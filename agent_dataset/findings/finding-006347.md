---
id: 6347
severity: "High"
---

# Claiming original allocation without staking rewards can lead to total loss of rewards

## Description

The Usual staking contract (UsualSP) has a vulnerability where users who claim their original vested allocation without first claiming their staking rewards can lose all accumulated rewards. This occurs because the vested allocations are considered staked and earn rewards, but claiming the original allocation removes the staking balance without updating the reward state.
In the UsualSP contract, vested allocations are treated as staked balances and earn staking rewards. However, the claimOriginalAllocation() function does not update the user's reward state before transferring the vested tokens. This can lead to a scenario where:
1. A user accumulates staking rewards on their vested allocation.
2. The user claims their original allocation using claimOriginalAllocation().
3. The user's staked balance becomes zero.
4. When trying to claim rewards with claimReward(), the transaction reverts due to insufficient balance.
As a result, the user loses all accumulated staking rewards.
Impact: The impact of this vulnerability is high. Users can potentially lose all of their accumulated staking rewards, which could be a significant amount depending on the vesting period and reward rate.
Likelihood: The likelihood of this issue occurring is medium to high. Users are likely to claim their original allocations as soon as they vest, and may not be aware that they need to claim rewards first. The non-intuitive order of operations increases the chances of users accidentally losing their rewards.

## Proof of Concept

```solidity
function testClaimReward_poc() public {
    uint256 rewardAmount = 100e18;
    uint256 vestedAmount = 300e18;
    setupStartOneDayRewardDistribution(rewardAmount);
    setupVestingWithOneYearCliff(vestedAmount);
    // Vested amount is seen as staked usualS balance
    assertEq(usualSP.balanceOf(alice), vestedAmount);
    // Skip to end
    skip(5 * 365 days);
    uint256 rate = rewardAmount / 1 days;
    uint256 rewardPerToken = rate * 1 days * 1e24 / usualSP.totalSupply();
    uint256 claimableRewardAmount = vestedAmount * rewardPerToken / 1e24;
    vm.startPrank(alice);
    // Scenario 1:
    // Alice first claims her $Usual rewards
    // Alice then claims her $UsualS allocation
    uint256 snap = vm.snapshot();
    usualSP.claimReward();
    usualSP.claimOriginalAllocation();
    assertEq(usualS.balanceOf(alice), vestedAmount);
    assertEq(usualToken.balanceOf(alice), claimableRewardAmount);
    // Scenario 2:
    // Alice first claims her $UsualS allocation
    // Alice then claims her $Usual rewards
    vm.revertTo(snap);
    usualSP.claimOriginalAllocation();
    vm.expectRevert(InsufficientUsualSAllocation.selector);
    usualSP.claimReward();
    // Alice loses all of her claimable rewards
    assertEq(usualS.balanceOf(alice), vestedAmount);
    assertEq(usualToken.balanceOf(alice), 0);
}
```

## Recommendation

To address this vulnerability, update the claimOriginalAllocation() function to include reward state updates before transferring the vested tokens. Additionally, remove the balance check from the claimReward() function to allow users to claim rewards even after their balance becomes zero.
```solidity
function claimReward() external nonReentrant whenNotPaused returns (uint256) {
    UsualSPStorageV0 storage $ = _usualSPStorageV0();
    if (block.timestamp < $.startDate + ONE_MONTH) {
        revert NotClaimableYet();
    }
    return _claimRewards();
}
```
```solidity
function claimOriginalAllocation() external nonReentrant whenNotPaused {
    UsualSPStorageV0 storage $ = _usualSPStorageV0();
    if ($.originalAllocation[msg.sender] == 0) {
        revert NotAuthorized();
    }
    // Update staking rewards
    _updateReward(msg.sender);
    uint256 amount = _available($, msg.sender);
    // slither-disable-next-line incorrect-equality
    if (amount == 0) {
        revert AlreadyClaimed();
    }
    $.originalClaimed[msg.sender] += amount;
    $.usualS.safeTransfer(msg.sender, amount);
    emit ClaimedOriginalAllocation(msg.sender, amount);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the way the Usual staking contract (UsualSP) handles the interaction between the original vested allocation and the staking reward accounting. In this contract the vested allocation is treated as a staked balance, meaning it continuously accrues rewards. The function claimOriginalAllocation transfers the vested tokens to the user but fails to update the user’s reward state before the transfer. As a result the user’s staked balance is reduced to zero while the internal reward accounting still assumes the user had a positive stake. When the user subsequently calls claimReward, the contract checks the current staked balance, finds it to be zero and reverts with an insufficient‑balance error. Consequently the user receives the original allocation but loses all previously earned rewards. The bug is triggered whenever a user claims the original allocation before claiming any accrued rewards, which is a natural order for many participants who wish to retrieve their vested tokens as soon as they become available. The affected parties are all token holders who have vested allocations in the UsualSP contract; they may lose a significant amount of rewards depending on the vesting period and reward rate. The issue was discovered during a formal audit when a test case demonstrated that claiming the allocation first caused the reward claim to revert and the reward balance to remain zero. The problem is subtle because the UI typically shows a successful allocation claim and does not warn that rewards are still pending, leading users to believe they have received the full entitlement. From a technical perspective the bug belongs to the class of accounting state‑update ordering errors, where a state‑changing operation (transfer of the original allocation) is performed before the dependent reward state is reconciled. This violates the business logic that rewards are earned on the amount that remains staked at the time of claim. To remediate the issue the claimOriginalAllocation function should invoke the internal reward‑update routine before transferring the vested tokens, ensuring the reward ledger reflects the final stake. Additionally, the reward‑claim function should not require a non‑zero staked balance after the original allocation has been withdrawn, allowing users to collect rewards even if their stake has been fully claimed. Implementing these changes restores the expected behavior where a user who claims the original allocation still receives all accrued rewards, aligning the contract with its intended accounting model.
