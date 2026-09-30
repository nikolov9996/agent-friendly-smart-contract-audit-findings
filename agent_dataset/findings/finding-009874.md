---
id: 9874
severity: "Medium"
---

# Remove splitter will always revert if there are some rewards left on splitter contract

## Description

```solidity
function addSplitter(
        address _account,
        LSTRewardsSplitter.Fee[] memory _fees
    ) external onlyOwner {
        if (address(splitters[_account]) != address(0)) revert SplitterAlreadyExists();

        address splitter = address(new LSTRewardsSplitter(lst, _fees, owner()));
        splitters[_account] = ILSTRewardsSplitter(splitter);
   ...
```
Stakelink users can register to share their LST rewards with other addresses through the LSTRewardsSplitterController contract. Upon registration, the user will set fee addresses, and an individual LSTRewardSplitter contract will be created for the user.

```solidity
   /**
@notice Splits new rewards
@param _rewardsAmount amount of new rewards
     */
    function splitRewards(uint256 rewardsAmount) private {
        for (uint256 i = 0; i < fees.length; ++i) {
            Fee memory fee = fees[i];
            uint256 amount = (_rewardsAmount * fee.basisPoints) / 10000;

            if (fee.receiver == address(lst)) {
                IStakingPool(address(lst)).burn(amount);
            } else {
                lst.safeTransfer(fee.receiver, amount);
            }
        }

        principalDeposits = lst.balanceOf(address(this));
        emit RewardsSplit(_rewardsAmount);
    }
```

When a user wants to remove a splitter, the removeSplitter function will be called on the LSTRewardsSplitterController. Upon removing the splitter, all rewards at that moment should be distributed to the fee addresses. However, if there are some rewards left, this will always fail because the controller contract will try to transfer the entire balance of the splitter contract to the user, including previously distributed rewards. This will revert because the balance is not reduced by the already distributed rewards.

```solidity
/**
@notice Removes an account's splitter
@param _account address of account
     **/
    function removeSplitter(address _account) external onlyOwner {
        ILSTRewardsSplitter splitter = splitters[_account];
        if (address(splitter) == address(0)) revert SplitterNotFound();

        uint256 balance = IERC20(lst).balanceOf(address(splitter));
        uint256 principalDeposits = splitter.principalDeposits();
        if (balance != 0) {
            if (balance != principalDeposits) splitter.splitRewards();
            splitter.withdraw(balance, _account);
        }
```

Vulnerable code: https://github.com/Cyfrin/2024-09-stakelink/blob/main/contracts/core/lstRewardsSplitter/LSTRewardsSplitterController.sol#L138

Likelihood: Medium

This will happen on every call to removeSplitter function inside LSTRewardsSplitterController if some rewards are accured.

Impact: Medium

The functionality of removing the splitter will be broken. The only way to remove the splitter would be to require that accrued rewards are zero. To ensure always correct functionality, the rewards would need to be distributed within the same block.

## Proof of Concept

```solidity
it('PoC:Medium:LSTRewardsSplitterController#134-138=>remove splitter will always revert if there are some rewards left on splitter contract', async () => {
    const { accounts, controller, token } = await loadFixture(deployFixture)

    // add new splitter for some account
    await controller.addSplitter(accounts[2], [
      { receiver: accounts[7], basisPoints: 4000 },
      { receiver: accounts[8], basisPoints: 4000 },
    ])

    // read newly created splitter
    const splitter = await ethers.getContractAt(
      'LSTRewardsSplitter',
      await controller.splitters(accounts[2])
    )

    // simulate reward amount
    const rewardAmount = toEther(100)
    await token.transfer(splitter.target, rewardAmount)
    
    // remove splitter will fail trying to transfer full balance amount without accounting for previous rewards distribution
    await expect(controller.removeSplitter(accounts[2])).to.be.reverted;
})
```

Running Poc:
Copy test to ./test/core/lst-rewards-splitter.test.ts
Run tests with npx hardhat test ./test/core/lst-rewards-splitter.test.ts --network hardhat

Output
```solidity
 LSTRewardsSplitter
    ✔ PoC:Medium:LSTRewardsSplitterController#134-138=>remove splitter does not work when there are some rewards left on splitter contract (1252ms)
```

## Recommendation

After splitRewards call, only lst balance left on splitter contract should be transfered to user. This amount is captured at the end of _splitRewardsFunction inside principalDeposits state variable.

```diff
/**
@notice Removes an account's splitter
@param _account address of account
     **/
    function removeSplitter(address _account) external onlyOwner {
        ILSTRewardsSplitter splitter = splitters[_account];
        if (address(splitter) == address(0)) revert SplitterNotFound();

        uint256 balance = IERC20(lst).balanceOf(address(splitter));
        uint256 principalDeposits = splitter.principalDeposits();
        if (balance != 0) {
            if (balance != principalDeposits) splitter.splitRewards();
            splitter.withdraw(balance, _account);
            splitter.withdraw(splitter.principalDeposits(), _account);
        }
```

A new test can be added to show that the functionality is now satisfied.

```solidity
it('remove splitter should work when some rewards are left on splitter contract', async () => {
    const { accounts, controller, token } = await loadFixture(deployFixture)

    // add new splitter for accounts[2]
    await controller.addSplitter(accounts[2], [
      { receiver: accounts[7], basisPoints: 4000 },
      { receiver: accounts[8], basisPoints: 4000 },
    ])

    // read newly created splitter
    const splitter = await ethers.getContractAt(
      'LSTRewardsSplitter',
      await controller.splitters(accounts[2])
    )

    // simulate reward amount
    const rewardAmount = toEther(100)
    await token.transfer(splitter.target, rewardAmount)

    // take snapshot before removing splitter
    const firstReceiverBalanceBefore = await token.balanceOf(accounts[7])
    const secondReceiverBalanceBefore = await token.balanceOf(accounts[8])
    const splitterBalanceBefore = await token.balanceOf(splitter.target)
    const splitterPrincipalDepositsBefore = await splitter.principalDeposits()
    const accountBalanceBefore = await token.balanceOf(accounts[2])

    console.log('\n=================BEFORE REMOVE SPLITTER====================')
    console.log('firstReceiverBalanceBefore', firstReceiverBalanceBefore.toString())
    console.log('secondReceiverBalanceBefore', secondReceiverBalanceBefore.toString())
    console.log('splitterBalanceBefore', splitterBalanceBefore.toString())
    console.log('splitterPrincipalDepositsBefore', splitterPrincipalDepositsBefore.toString())
    console.log('accountBalanceBefore', accountBalanceBefore.toString())

    // make sure splitter has 'rewardAmount' to distribute
    assert.equal(splitterBalanceBefore - splitterPrincipalDepositsBefore, BigInt(rewardAmount))

    // remove splitter
    await controller.removeSplitter(accounts[2])

    const firstReceiverBalanceAfter = await token.balanceOf(accounts[7])
    const secondReceiverBalanceAfter = await token.balanceOf(accounts[8])
    const splitterBalanceAfter = await token.balanceOf(splitter.target)
    const accountBalanceAfter = await token.balanceOf(accounts[2])

    console.log('\n=================AFTER REMOVE SPLITTER====================')
    console.log('firstReceiverBalanceAfter', firstReceiverBalanceAfter.toString())
    console.log('secondReceiverBalanceAfter', secondReceiverBalanceAfter.toString())
    console.log('splitterBalanceAfter', splitterBalanceAfter.toString())
    console.log('accountBalanceAfter', accountBalanceAfter.toString())

    // show that rewards were distributed correctly and no funds were left on splitter contract
    assert.equal(firstReceiverBalanceAfter - firstReceiverBalanceBefore, BigInt(rewardAmount) * 4n / 10n)
    assert.equal(secondReceiverBalanceAfter - secondReceiverBalanceBefore, BigInt(rewardAmount) * 4n / 10n)
    assert.equal(splitterBalanceAfter, 0n)
    assert.equal(accountBalanceAfter, accountBalanceBefore + BigInt(rewardAmount) * 2n / 10n)
  })
```

Output:
```solidity
LSTRewardsSplitter

=================BEFORE REMOVE SPLITTER====================
firstReceiverBalanceBefore 0
secondReceiverBalanceBefore 0
splitterBalanceBefore 100000000000000000000
splitterPrincipalDepositsBefore 0
accountBalanceBefore 10000000000000000000000

=================AFTER REMOVE SPLITTER====================
firstReceiverBalanceAfter 40000000000000000000
secondReceiverBalanceAfter 40000000000000000000
splitterBalanceAfter 0
accountBalanceAfter 10020000000000000000000
    ✔ remove splitter should work when some rewards are left on splitter contract (1286ms)

  1 passing (1s)
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the LSTRewardsSplitterController.removeSplitter function, which is intended to delete a user‑specific splitter and return any remaining token balance to the user. The function reads the total token balance of the splitter contract and the value stored in the splitter’s principalDeposits variable, then attempts to withdraw the full balance. However, when rewards have been accrued, the splitter’s splitRewards routine has already transferred a portion of the balance to the configured fee receivers, while the principalDeposits state variable still reflects the pre‑distribution total. Consequently the balance held by the splitter contract is lower than the principalDeposits value, and the subsequent withdraw call requests more tokens than are actually available. This mismatch triggers a revert, causing the removeSplitter transaction to fail. The bug can be exploited simply by invoking removeSplitter while any rewards are pending; the call will always revert, preventing the splitter from being removed and effectively locking the user’s principal deposit and any undistributed rewards. The impact is that users cannot cleanly deregister their splitter, the protocol’s administrative functions become unusable for affected accounts, and funds may remain inaccessible until the rewards balance is manually cleared to zero. The condition occurs whenever rewards have been accrued but not yet split in the same block, which is a common situation in normal operation. The issue was discovered during a security audit that exercised the removeSplitter path with simulated reward deposits and observed a revert. It is subtle because the code appears to check for a non‑zero balance before withdrawing, yet it does not account for the fact that part of that balance may already have been sent out, leading to an accounting inconsistency that is not obvious from the surface logic. The bug belongs to the class of accounting‑state‑mismatch vulnerabilities where stored accounting variables diverge from actual contract balances, often resulting in failed transfers or locked assets. From a user’s perspective the UI would show a “Remove splitter” action that suddenly fails with a transaction revert, leaving the user’s funds unchanged and possibly displaying an unexpected error. The expected behavior is that the splitter is removed and the user receives their remaining principal plus any undistributed rewards; the reality is that the transaction reverts and no funds move. To remediate the issue the controller should withdraw only the amount that actually remains after rewards have been distributed, for example by calling splitRewards first and then withdrawing the updated principalDeposits, or by separating the withdrawal of the principal from the withdrawal of any residual balance, ensuring that the amount requested from the splitter never exceeds its current token balance.
