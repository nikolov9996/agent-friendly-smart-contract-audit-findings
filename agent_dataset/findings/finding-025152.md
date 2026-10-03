---
id: 25152
severity: "Medium"
---

# Having no deposits in StakedEXA will lead to stuck rewards when harvesting

## Description



## Proof of Concept

In `StakedEXA::updateIndex()`, the index is updated to `globalIndex(reward);` and `rewardData.updatedAt` to the current `block.timestamp` or `rewardData.finishAt`.

```solidity
function updateIndex(IERC20 reward) internal {
  RewardData storage rewardData = rewards[reward];
  rewardData.index = globalIndex(reward);
  rewardData.updatedAt = uint40(lastTimeRewardApplicable(rewardData.finishAt));
}
```

In `StakedEXA::globalIndex()`, the index is not increased if the total supply is null:

```solidity
function globalIndex(IERC20 reward) public view returns (uint256) {
  RewardData storage rewardData = rewards[reward];
  if (totalSupply() == 0) return rewardData.index;

  return
    rewardData.index +
    (rewardData.rate * (lastTimeRewardApplicable(rewardData.finishAt) - rewardData.updatedAt)).divWadDown(
      totalSupply()
    );
}
```

Thus, as can be seen, the index will not be updated by `rewardData.updatedAt` is increased, losing these rewards forever.

## Impact

Stuck rewards as the index is not increased but `rewardData.updatedAt` increases.

## Recommendation

If the total supply is null the amount not distributed can be calculated by doing `rate x deltaTime` and send to savings.
