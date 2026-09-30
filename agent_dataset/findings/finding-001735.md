---
id: 1735
severity: "Medium"
---

# Delegators can lose their re-wards when a delegator has removed a del-egatee and claims all of his rewards before delegating again to a previous removed delegatee. Found by 0xStalin

## Description

The loss of funds is the result of two bugs, which are:
1. The first bug occurs when a delegator claims all his rewards after he removed one of his delegatees. When claiming all the rewards after a delegator has removed a delegatee, the undelegated delegatee is removed from the AddressSet of delegatees.
• The problem is that when a delegatee is removed, the length of the AddressSet is reduced, which affects the total number of delegatees that will be iterated to claim the rewards. As the AddressSet shrinks, the i variable controlling the iterations of the for loop grows, which at some point, i will be equal to the new length of the shrunk AddressSet, causing the for loop to exit the iteration and leaving some delegatees without claiming their rewards.
```solidity
function claimAll(address delegator, uint256 targetEpochIndex) external onlyL2StakingContract {
    ...
    // shrinks each time an undelegated delegatee is found!
    for (uint256 i = 0; i < unclaimed[delegator].delegatees.length(); i++) {
        address delegatee = unclaimed[delegator].delegatees.at(i);
        if (
            unclaimed[delegator].delegatees.contains(delegatee) &&
            unclaimed[delegator].unclaimedStart[delegatee] <= endEpochIndex
        ) {
            // endEpochIndex, the delegatee will be removed from the delegatees AddressSet
            // the Set to shrink!
            reward += _claim(delegatee, delegator, endEpochIndex);
        }
    }
    ...
}
function _claim(address delegatee, address delegator, uint256 endEpochIndex) internal returns (uint256 reward) {
    ...
    for (uint256 i = unclaimed[delegator].unclaimedStart[delegatee]; i <= endEpochIndex; i++) {
        ...
        // if undelegated, remove delegator unclaimed info after claimed all
        if (unclaimed[delegator].undelegated[delegatee] && unclaimed[delegator].unclaimedEnd[delegatee] == i) {
            // Set to shrink!
            unclaimed[delegator].delegatees.remove(delegatee);
            delete unclaimed[delegator].undelegated[delegatee];
            delete unclaimed[delegator].unclaimedStart[delegatee];
            delete unclaimed[delegator].unclaimedEnd[delegatee];
            break;
        }
    }
    ...
}
```
Find below a simple PoC where it is demonstrated this bug. It basically adds and undelegates some delegatees to one delegator, then, the delegator claims all of his rewards, and, because the delegator has some undelegated delegatees, the bug will occur causing the function to not claim the rewards of all the delegatees.
• Create a new file on the test/ folder and add the below code to it:
```solidity
pragma solidity ^0.8.13;
import {EnumerableSetUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/structs/EnumerableSetUpgradeable.sol";
import {Test, console2} from "forge-std/Test.sol";
contract SimpleDelegations {
    using EnumerableSetUpgradeable for EnumerableSetUpgradeable.AddressSet;
    struct Unclaimed {
        EnumerableSetUpgradeable.AddressSet delegatees;
        mapping(address => bool) undelegated;
        // mapping(address => uint256) unclaimedStart;
        // mapping(address => uint256) unclaimedEnd;
    }
    mapping(address => Unclaimed) private unclaimed;
    function addDelegatee(address delegatee) external {
        unclaimed[msg.sender].delegatees.add(delegatee);
    }
    function undelegate(address delegatee) external {
        unclaimed[msg.sender].undelegated[delegatee] = true;
    }
    // will be removed from the delegator in `_claim()`, which makes the `unclaimed.delegatees` AddressSet length to shrink, which unintentionally causes the for loop to do less iterations than the original amount of delegatees at the beginning of the call!
    function claimAll() external returns (uint256 reward) {
        for (uint256 i = 0; i < unclaimed[msg.sender].delegatees.length(); i++) {
            console2.log("delegatees.length: ", unclaimed[msg.sender].delegatees.length());
            address delegatee = unclaimed[msg.sender].delegatees.at(i);
            // console2.log("i: ", i);
            console2.log("delegatee: ", delegatee);
            if (
                unclaimed[msg.sender].delegatees.contains(delegatee)
                // unclaimed[delegator].unclaimedStart[delegatee] <= endEpochIndex
            ) {
                reward += _claim(delegatee, msg.sender);
            }
        }
    }
    // function claimAll() external returns (uint256 reward) {
    //     uint256 totalDelegatees = unclaimed[msg.sender].delegatees.length();
    //     address[] memory delegatees = new address[](totalDelegatees);
    //     for (uint256 i = 0; i < unclaimed[msg.sender].delegatees.length(); i++) {
    //         delegatees[i] = unclaimed[msg.sender].delegatees.at(i);
    //     }
    // removed from the AddressSet, the for loop will still iterate over all the delegatees at the start of the call!
    //     for (uint256 i = 0; i < delegatees.length; i++) {
    //         // console2.log("delegatee: ", delegatees[i]);
    //         if (
    //             unclaimed[msg.sender].delegatees.contains(delegatees[i])
    //             // unclaimed[delegator].unclaimedStart[delegatees[i]] <= endEpochIndex
    //         ) {
    //             reward += _claim(delegatees[i], msg.sender);
    //         }
    //     }
    // }
    function _claim(address delegatee, address delegator) internal returns(uint256 reward) {
        require(unclaimed[delegator].delegatees.contains(delegatee), "no remaining reward");
        reward = 10;
        // delegatees!
        if (unclaimed[delegator].undelegated[delegatee]) {
            // causing the for loop to not iterate over all the delegatees!
            unclaimed[delegator].delegatees.remove(delegatee);
            delete unclaimed[delegator].undelegated[delegatee];
        }
    }
    function getDelegatees() external view returns (address[] memory) {
        return unclaimed[msg.sender].delegatees.values();
    }
}
contract BugWhenClaimingAllRewards is Test {
    function test_claimingAllRewardsReproducingBug() public {
        SimpleDelegations delegations = new SimpleDelegations();
        delegations.addDelegatee(address(1));
        delegations.addDelegatee(address(2));
        delegations.addDelegatee(address(3));
        delegations.undelegate(address(1));
        delegations.undelegate(address(3));
        // delegatee gives 10 rewards
        uint256 rewards = delegations.claimAll();
        console2.log("Total rewards: ", rewards);
        console2.log("delegatees list after claiming");
        address[] memory delegatees = delegations.getDelegatees();
        for(uint i = 0; i < delegatees.length; i++) {
            console2.log("delegatee: ", delegatees[i]);
        }
        // would have been deleted from the `unclaimed.delegatees` AddressSet, but because the delegatee 3 was never reached, (and the rewards of this delegatee were not claimed), this delegatee is still part of the list of delegatees for the delegator with unclaimed rewards!
    }
}
```
Run the previous PoC with the next command: forge test --match-test test_claimingAllRewardsReproducingBug -vvvv
PoC will be a full coded PoC working with the contracts of the system where the full scenario that causes the users to lose their rewards is reproduced.
2. The second bug occurs when a delegator delegates to a previously undelegated delegatee. When delegating to a previously undelegated delegatee, the logic does not check if there are any pending rewards of this delegatee to be claimed, it simply updates it to the effectiveEpoch.
```solidity
function notifyDelegation(
    ...
    uint256 effectiveEpoch,
    ...
) public onlyL2StakingContract {
    ...
    // update unclaimed info
    if (newDelegation) {
        unclaimed[delegator].delegatees.add(delegatee);
        // sets the `unclaimedStart` to be effectiveEpoch.
        unclaimed[delegator].unclaimedStart[delegatee] = effectiveEpoch;
    }
}
```
Setting the unclaimedStart without verifying if there are any pending rewards causes that rewards can only be claimed starting at the effectiveEpoch, any pending rewards that were earned prior to the effectiveEpoch will be lost, since the _claim function enforces that the epoch been claimed must not be less than the unclaimedStart.
```solidity
function _claim(address delegatee, address delegator, uint256 endEpochIndex) internal returns (uint256 reward) {
    require(unclaimed[delegator].delegatees.contains(delegatee), "no remaining reward");
    // onwards!
    require(unclaimed[delegator].unclaimedStart[delegatee] <= endEpochIndex, "all reward claimed");
}
```
As we will see in the next coded PoC, the user did everything correctly, he claimed all of his rewards, but due to the first bug, some rewards were left unclaimed. And then, the user claims his undelegation for an undelegated delegatee, afterwards, he proceeded to delegate a lower amount to an undelegated delegatee. The combination of the two bugs is what causes the loss of the rewards that were not claimed when the user indicated to claim all of his rewards. The user did not make any mistake, the bugs present on the contract caused the user to lose his rewards.
Bug when claiming all delegator's rewards after a delegatee(s) were removed.
Bug when a delegator delegates to a delegatee that was previously undelegated.
Internal pre-conditions
User claims all his rewards after one or more delegatees were removed, and afterwards, it delegates to a delegatee that was previously removed.
External pre-conditions
none
Attack Path
1. Delegator undelegates to one or more of his delegatees.
2. Delegator claims all of his rewards.
3. Delegator claims his undelegations on the L2Staking contract.
4. Delegator delegates again to a previous removed delegatee.
User's rewards are lost and become unclaimable, those rewards get stuck on the Distribute contract.

## Proof of Concept

Add the next PoC in the test file:
```solidity
function test_DelegatorLosesRewardsPoC() public {
    hevm.startPrank(alice);
    morphToken.approve(address(l2Staking), type(uint256).max);
    l2Staking.delegateStake(firstStaker, 5 ether);
    l2Staking.delegateStake(secondStaker, 5 ether);
    hevm.stopPrank();
    hevm.startPrank(bob);
    morphToken.approve(address(l2Staking), type(uint256).max);
    l2Staking.delegateStake(firstStaker, 5 ether);
    l2Staking.delegateStake(secondStaker, 5 ether);
    l2Staking.delegateStake(thirdStaker, 5 ether);
    hevm.stopPrank();
    uint256 time = REWARD_EPOCH;
    hevm.warp(time);
    hevm.prank(multisig);
    l2Staking.startReward();
    // staker set commission
    hevm.prank(firstStaker);
    l2Staking.setCommissionRate(1);
    hevm.prank(secondStaker);
    l2Staking.setCommissionRate(1);
    hevm.prank(thirdStaker);
    l2Staking.setCommissionRate(1);
    // *************** epoch = 1 ******************** //
    time = REWARD_EPOCH * 2;
    hevm.warp(time);
    uint256 blocksCountOfEpoch = REWARD_EPOCH / 3;
    hevm.roll(blocksCountOfEpoch * 2);
    hevm.prank(oracleAddress);
    record.setLatestRewardEpochBlock(blocksCountOfEpoch);
    _updateDistribute(0);
    // *************** epoch = 2 ******************** //
    time = REWARD_EPOCH * 3;
    hevm.roll(blocksCountOfEpoch * 3);
    hevm.warp(time);
    _updateDistribute(1);
    // *************** epoch = 3 ******************** //
    time = REWARD_EPOCH * 4;
    hevm.roll(blocksCountOfEpoch * 4);
    hevm.warp(time);
    _updateDistribute(2);
    uint256 bobReward1;
    uint256 bobReward2;
    uint256 bobReward3;
    {
        (address[] memory delegetees, uint256[] memory bobRewards) = distribute.queryAllUnclaimed(bob);
        bobReward1 = distribute.queryUnclaimed(firstStaker, bob);
        bobReward2 = distribute.queryUnclaimed(secondStaker, bob);
        bobReward3 = distribute.queryUnclaimed(thirdStaker, bob);
        assertEq(delegetees[0], firstStaker);
        assertEq(delegetees[1], secondStaker);
        assertEq(delegetees[2], thirdStaker);
        assertEq(bobRewards[0], bobReward1);
        assertEq(bobRewards[1], bobReward2);
        assertEq(bobRewards[2], bobReward3);
    }
    // *************** epoch = 4 ******************** //
    time = REWARD_EPOCH * 5;
    hevm.roll(blocksCountOfEpoch * 5);
    hevm.warp(time);
    _updateDistribute(3);
    // !
    hevm.startPrank(bob);
    l2Staking.undelegateStake(firstStaker);
    l2Staking.undelegateStake(thirdStaker);
    // l2Staking.undelegateStake(secondStaker);
    IL2Staking.Undelegation[] memory undelegations = l2Staking.getUndelegations(bob);
    assertEq(undelegations.length, 2);
    // *************** epoch = 5 ******************** //
    time = REWARD_EPOCH * 6;
    hevm.roll(blocksCountOfEpoch * 6);
    hevm.warp(time);
    _updateDistribute(4);
    time = rewardStartTime + REWARD_EPOCH * (ROLLUP_EPOCH + 5);
    hevm.warp(time);
    bobReward1 = distribute.queryUnclaimed(firstStaker, bob);
    bobReward2 = distribute.queryUnclaimed(secondStaker, bob);
    bobReward3 = distribute.queryUnclaimed(thirdStaker, bob);
    hevm.startPrank(bob);
    uint256 balanceBefore = morphToken.balanceOf(bob);
    l2Staking.claimReward(address(0), 0);
    uint256 balanceAfter = morphToken.balanceOf(bob);
    // rewards that Bob has earned.
    assert(balanceAfter < balanceBefore + bobReward1 + bobReward2 + bobReward3);
    l2Staking.claimUndelegation();
    // undelegated in the past
    // after he delegates to the 3rd staker (because the bug when claiming all the rewards while the delegator has undelegated delegatees), in combination with the bug when delegating to a delegatee that the user has pending rewards to claim.
    uint256 bobRewardsBeforeLosing;
    {
        (address[] memory delegetees, uint256[] memory bobRewards) = distribute.queryAllUnclaimed(bob);
        for(uint i = 0; i < bobRewards.length; i++) {
            bobRewardsBeforeLosing += bobRewards[i];
        }
    }
    // the thirdStaker
    uint256 bobMorphBalanceBeforeDelegating = morphToken.balanceOf(bob) - 1 ether;
    // delegation
    l2Staking.delegateStake(thirdStaker, 1 ether);
    uint256 bobRewardsAfterLosing;
    {
        (address[] memory delegetees, uint256[] memory bobRewards) = distribute.queryAllUnclaimed(bob);
        for(uint i = 0; i < bobRewards.length; i++) {
            bobRewardsAfterLosing += bobRewards[i];
        }
    }
    uint256 bobMorphBalanceAfterDelegating = morphToken.balanceOf(bob);
    // delegation to the 3rd staker.
    assert(bobRewardsBeforeLosing > bobRewardsAfterLosing && bobMorphBalanceBeforeDelegating == bobMorphBalanceAfterDelegating);
}
```
Run the previous PoC with the next command: forge test --match-test test_DelegatorLosesRewardsPoC -vvvv

## Recommendation

Since there are two bugs involved in this problem, it is required to fix each of them.
The mitigation for the first bug (problem when claiming all the rewards):
• Refactor the function as follows:
```solidity
function claimAll(address delegator, uint256 targetEpochIndex) external returns (uint256 reward) {
    require(mintedEpochCount != 0, "not minted yet");
    uint256 endEpochIndex = (targetEpochIndex == 0 || targetEpochIndex > mintedEpochCount - 1)
        ? mintedEpochCount - 1
        : targetEpochIndex;
    uint256 reward;
    uint256 totalDelegatees = unclaimed[delegator].delegatees.length();
    address[] memory delegatees = new address[](totalDelegatees);
    for (uint256 i = 0; i < unclaimed[delegator].delegatees.length(); i++) {
        delegatees[i] = unclaimed[delegator].delegatees.at(i);
    }
    // removed from the AddressSet, the for loop will still iterate over all the delegatees at the start of the call!
    for (uint256 i = 0; i < delegatees.length; i++) {
        if (
            unclaimed[delegator].delegatees.contains(delegatees[i]) &&
            unclaimed[delegator].unclaimedStart[delegatee] <= endEpochIndex
        ) {
            reward += _claim(delegatees[i], delegator);
        }
    }
    if (reward > 0) {
        _transfer(delegator, reward);
    }
}
```
The mitigation for the second bug (delegating to a previous undelegated delegatee causes all pending rewards to be lost):
• Before setting the effectiveEpoch, check if there is any pending rewards, and if there are any, either revert the tx or proceed to claim the rewards of the delegatee on behalf of the delegator.
```solidity
function notifyDelegation(
    ...
) public onlyL2StakingContract {
    ...
    // update unclaimed info
    if (newDelegation) {
        // does not have any pending rewards to claim on the delegatee!
        if(unclaimed[delegator].undelegated[delegatee] && unclaimed[delegator].unclaimedEnd[delegatee] != 0) {
            // the epoch when the delegator undelegated the delegatee!
            uint256 rewards = _claim(delegatee, delegator, effectiveEpoch - 1);
            if (reward > 0) {
                _transfer(delegator, reward);
            }
        }
        unclaimed[delegator].delegatees.add(delegatee);
        unclaimed[delegator].unclaimedStart[delegatee] = effectiveEpoch;
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

A delegator can lose earned rewards due to the interaction of two logical bugs in the reward‑claiming and delegation workflow. The first bug appears in the function that claims all pending rewards for a delegator. The contract stores the set of delegatees in an EnumerableSet and iterates over it with a for‑loop that uses the current length of the set as its upper bound. When a delegatee has been undelegated, the claim routine removes that delegatee from the set during the same iteration. Because the set shrinks, the loop counter eventually reaches the new, smaller length and the loop terminates early, leaving the remaining delegatees unprocessed and their rewards unclaimed. The second bug occurs when a delegator later re‑delegates to a delegatee that was previously undelegated. The delegation logic records a new unclaimedStart epoch equal to the effective epoch of the new delegation without checking whether the delegatee still has pending rewards from earlier epochs. The internal _claim function requires the claimed epoch to be greater than or equal to unclaimedStart, so any rewards earned before the effective epoch become permanently inaccessible. The attack path is: (1) the delegator undelegates one or more delegatees, (2) calls claimAll, which skips rewards for some delegatees because the set shrinks, (3) claims the undelegation, (4) re‑delegates to a previously removed delegatee, which resets the accounting window and discards the unclaimed rewards that were missed in step 2. From the user’s perspective the UI shows a successful claim transaction but the token balance increases by less than the expected amount; later the user sees zero reward for a delegatee that should still have pending rewards. The impact is a loss of funds that become stuck in the distribution contract, violating the protocol’s accounting assumptions that all earned rewards are claimable. The issue was discovered by the auditor 0xStalin through manual code inspection and a reproducible proof‑of‑concept test that demonstrated missing rewards after the described sequence. The bug is hard to notice because the loop does not revert or emit an error; it simply stops iterating, so developers may assume all delegatees were processed. The vulnerability belongs to the class of mutable‑collection‑iteration bugs (modifying a data structure while iterating over it) combined with improper state reset that leads to accounting loss. To fix the first bug the contract should snapshot the delegatee list into a fixed‑size array before iterating, or avoid removing entries during the loop. To fix the second bug the delegation routine must check for any pending rewards for the delegatee before overwriting unclaimedStart, either by claiming those rewards or by reverting the transaction. Both fixes restore the guarantee that a delegator’s rewards are fully claimable and that re‑delegation does not erase previously earned amounts.
