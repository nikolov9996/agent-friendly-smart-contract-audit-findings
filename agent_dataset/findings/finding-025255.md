---
id: 25255
severity: "Medium"
---

# Wrong reward distribution between early and late depositors because of the late syncRewards() call in the cycle, syncReward() logic should be executed in each withdraw or deposits (without reverting)

## Description



## Proof of Concept

This is `syncRewards()` code:

function syncRewards() public { uint32 timestamp = block.timestamp.safeCastTo32();

if (timestamp < rewardsCycleEnd) { revert SyncError(); }

uint192 lastRewardsAmt_ = lastRewardsAmt; uint256 totalReleasedAssets_ = totalReleasedAssets; uint256 stakingTotalAssets_ = stakingTotalAssets;

uint256 nextRewardsAmt = (asset.balanceOf(address(this)) + stakingTotalAssets_) - totalReleasedAssets_ - lastRewardsAmt_;

// Ensure nextRewardsCycleEnd will be evenly divisible by `rewardsCycleLength`. uint32 nextRewardsCycleEnd = ((timestamp + rewardsCycleLength) / rewardsCycleLength) * rewardsCycleLength;

lastRewardsAmt = nextRewardsAmt.safeCastTo192(); lastSync = timestamp; rewardsCycleEnd = nextRewardsCycleEnd; totalReleasedAssets = totalReleasedAssets_ + lastRewardsAmt_; emit NewRewardsCycle(nextRewardsCycleEnd, nextRewardsAmt); }

As you can see whenever this function is called it starts the new cycle and sets the end of the cycle to the next multiple of the `rewardsCycleLength` and it release the rewards linearly between current timestamp and cycle end time. So if `syncRewards()` get called near to multiple of the `rewardsCycleLength` then rewards would be distributed with higher speed in less time. The problem is that users depositing funds before call `syncRewards()` won't receive new cycles rewards and early depositing won't get considered in reward distribution if deposits happen before `syncRewards()` call and if a user withdraws his funds before the `syncRewards()` call then he receives no rewards.

Imagine this scenario:

1. `rewardsCycleLength` is 10 days and the rewards for the next cycle is `100` AVAX.
2. the last cycle has been ended and user1 has `10000` AVAX deposited and has 50% of the pool shares.
3. `syncRewards()` don't get called for 8 days.
4. users1 withdraws his funds receive `10000` AVAX even so he deposits for 8 days in the current cycle.
5. users2 deposit `1000` AVAX and get 10% of pool shares and the user2 would call `syncRewards()` and contract would start distributing `100` avax as reward.
6. after 2 days cycle would finish and user2 would receive `100 * 10% = 10` AVAX as rewards for his `1000` AVAX deposit for 2 days but user1 had `10000` AVAX for 8 days and would receive 0 rewards.

So rewards won't distribute fairly between depositors across the time and any user interacting with contract before the `syncRewards()` call can lose his rewards. Contract won't consider deposit amounts and duration before `syncRewards()` call and it won't make sure that `syncRewards()` logic would be executed as early as possible with deposit or withdraw calls when a cycle ends.

## Recommendation

One way to solve this is to call `syncRewards()` logic in each deposit or withdraw and make sure that cycles start as early as possible (the revert "SyncError()" in the `syncRewards()` should be removed for this).
