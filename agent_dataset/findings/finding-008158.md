---
id: 8158
severity: "High"
---

# Loss of funds for a user due to incorrect state updates while unstaking

## Description

In the staking contract, users can withdraw their staked tokens after a 6-epoch waiting period if unstaking from any of the past epochs, or immediately if unstaking from the current epoch. However, a critical issue arises when users attempt to unstake tokens from earlier epochs while they have previously staked in the current epoch. In this scenario, the contract fails to correctly update the unredeemedEpoch variable. This malfunction results in users losing access to their staked funds and accumulated rewards.

FjordStaking.sol#L478

FjordStaking.sol#L540

The problem arises in the FjordStaking::unstake() and FjordStaking::_unstakeVested() when user requests unstake of fully amount (dr.staked and dr.vestedStaked will be 0) from any of the previous epochs, while previously staked in the current epoch. More precisely, in this scenario, userData[userAddress].unredeemedEpoch is set to 0, even tough user is unstaking from previous epoch and not the current one.

Specifically, when a user attempts to unstake tokens from an earlier epoch (i.e., any epoch other than the current one) after having staked additional tokens in the current epoch, the contract erroneously resets unredeemedEpoch to 0.

The root cause of the issue lies in the logic that does not differentiate between unstaking from the current epoch and previous epochs, leading to the unintended reset of the unredeemedEpoch variable.

PoC
Place the following test in test/unit/unstake.t.sol:
```solidity
function testLossOfFunds() public {
    address user=makeAddr("user");
    deal(address(token),user,2 ether);

    uint256 epoch = fjordStaking.currentEpoch();
    console.log("First stake epoch:", epoch);

    vm.startPrank(user);
    token.approve(address(fjordStaking), 1 ether);
    fjordStaking.stake(1 ether);
    vm.stopPrank();

    vm.startPrank(minter);
    for (uint256 i = 0; i < 7; i++) {
        vm.warp(vm.getBlockTimestamp() + fjordStaking.epochDuration());
        fjordStaking.addReward(1 ether);
    }
    vm.stopPrank();

    uint256 epochAfter = fjordStaking.currentEpoch();
    console.log("Second stake epoch: ", epochAfter); //After the second stake, user also unstakes firstly stacked tokens

    vm.startPrank(user);
    token.approve(address(fjordStaking), 1 ether);
    fjordStaking.stake(1 ether); // so user stakes tokens in current epoch and then unstakes from the first epoch
    fjordStaking.unstake(1, 1 ether);
    vm.stopPrank();

    vm.warp(vm.getBlockTimestamp() + 7 * fjordStaking.epochDuration());
    vm.prank(minter);
    fjordStaking.addReward(1 ether);
    epochAfter = fjordStaking.currentEpoch();

    vm.prank(user);
    vm.expectRevert();
    // the next line reverts due to arithmetic underflow in the following line
    // <https://github.com/Cyfrin/2024-08-fjord/blob/0312fa9dca29fa7ed9fc432fdcd05545b736575d/src/FjordStaking.sol#L472>
    fjordStaking.unstake(8,1 ether);
}
```
The impact of this vulnerability is significant, as it prevents users from accessing their staked tokens and accumulated rewards which will remain locked in the FjordStaking contract. This means that users lose access to newly staked tokens and any rewards that will be earned in the future epochs, potentially leading to a substantial financial loss.

## Proof of Concept

Place the following test in test/unit/unstake.t.sol:
```solidity
function testLossOfFunds() public {
    address user=makeAddr("user");
    deal(address(token),user,2 ether);

    uint256 epoch = fjordStaking.currentEpoch();
    console.log("First stake epoch:", epoch);

    vm.startPrank(user);
    token.approve(address(fjordStaking), 1 ether);
    fjordStaking.stake(1 ether);
    vm.stopPrank();

    vm.startPrank(minter);
    for (uint256 i = 0; i < 7; i++) {
        vm.warp(vm.getBlockTimestamp() + fjordStaking.epochDuration());
        fjordStaking.addReward(1 ether);
    }
    vm.stopPrank();

    uint256 epochAfter = fjordStaking.currentEpoch();
    console.log("Second stake epoch: ", epochAfter); //After the second stake, user also unstakes firstly stacked tokens

    vm.startPrank(user);
    token.approve(address(fjordStaking), 1 ether);
    fjordStaking.stake(1 ether); // so user stakes tokens in current epoch and then unstakes from the first epoch
    fjordStaking.unstake(1, 1 ether);
    vm.stopPrank();

    vm.warp(vm.getBlockTimestamp() + 7 * fjordStaking.epochDuration());
    vm.prank(minter);
    fjordStaking.addReward(1 ether);
    epochAfter = fjordStaking.currentEpoch();

    vm.prank(user);
    vm.expectRevert();
    // the next line reverts due to arithmetic underflow in the following line
    // <https://github.com/Cyfrin/2024-08-fjord/blob/0312fa9dca29fa7ed9fc432fdcd05545b736575d/src/FjordStaking.sol#L472>
    fjordStaking.unstake(8,1 ether);
}
```

## Recommendation

Add checks that will take into account that unredeemedEpoch should be set to 0 only if the currentEpoch == _epoch :
```solidity
function unstake(uint16 epoch, uint256 amount)
        external
        checkEpochRollover
        redeemPendingRewards
        returns (uint256 total)
    {
        // ...
        if (dr.staked == 0 && dr.vestedStaked == 0) {
            // no longer a valid unredeemed epoch
            if (userData[msg.sender].unredeemedEpoch == currentEpoch && _epoch == currentEpoch) {
                userData[msg.sender].unredeemedEpoch = 0;
            }
            delete deposits[msg.sender][_epoch];
            activeDeposits[msg.sender].remove(epoch);
        }
        // ...
    }
```
```solidity
function unstakeVested(address streamOwner, uint256 streamID, uint256 amount) internal {
        // ...
        if (dr.vestedStaked == 0 && dr.staked == 0) {
            // instant unstake
            if (userData[streamOwner].unredeemedEpoch == currentEpoch && data.epoch == currentEpoch) {
                userData[streamOwner].unredeemedEpoch = 0;
            }
            delete deposits[streamOwner][data.epoch];
            _activeDeposits[streamOwner].remove(data.epoch);
        }
        // ...
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

During unstaking the contract tracks an unredeemedEpoch value that indicates the earliest epoch from which a user still has tokens that can be claimed. When a user stakes in the current epoch and later tries to unstake the full amount that was originally deposited in a previous epoch, the unstake logic clears the deposit record but does not correctly preserve the unredeemedEpoch because the code treats any zero‑balance deposit as belonging to the current epoch. As a result the variable is reset to zero even though the user is withdrawing from an earlier epoch. This mismatch causes subsequent calls to the reward‑distribution functions to reference a non‑existent epoch, leading to arithmetic underflow and a revert. From the user’s perspective the staked balance appears to be zero, the UI shows no tokens available for withdrawal, and any accrued rewards remain locked forever. The bug only manifests when a user has active stakes in both the current epoch and one or more past epochs and attempts to withdraw the past stake before the waiting period for the current stake has elapsed. It was discovered during a targeted unit‑test that simulated staking in two epochs and then calling unstake on the first epoch; the test observed that the second unstake reverted due to an underflow. The issue is hard to notice because the contract does not emit an explicit error when the unredeemedEpoch is cleared, and the UI may simply show a zero balance without explaining why rewards cannot be claimed. The vulnerability belongs to the class of state‑inconsistency bugs where epoch‑based accounting variables are not correctly updated after partial withdrawals. The business logic assumes that unredeemedEpoch is only cleared when the user has no remaining deposits in any epoch, but the implementation violates that assumption. To fix the problem the contract must add a condition that only resets unredeemedEpoch when the cleared deposit belongs to the current epoch, leaving the value unchanged for earlier epochs, and must ensure that deposit records are deleted after the appropriate checks. Proper checks and tests should be added to verify that unredeemedEpoch remains accurate after mixed‑epoch unstaking.
