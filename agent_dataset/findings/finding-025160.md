---
id: 25160
severity: "Medium"
---

# Anyone will DoS setting a new rewards duration which harms the protocol/users as they will receive too much or too little rewards

## Description



## Proof of Concept

The function `StakedEXA::setRewardsDistribution()` shows that it's not possible to update the duration if the current reward period is not finished:

```solidity
function setRewardsDuration(IERC20 reward, uint40 duration) public onlyRole(DEFAULT_ADMIN_ROLE) {
  RewardData storage rewardData = rewards[reward];
  if (rewardData.finishAt > block.timestamp) revert NotFinished(); //@audit DoS this

  rewardData.duration = duration;

  emit RewardsDurationSet(reward, msg.sender, duration);
}
```

`StakedEXA::harvest()` notifies new rewards, which updates the current reward period finish, making it impossible to change the duration.

## Recommendation

The duration can be set by carefully adjusting the current reward rate to reflect the new duration. One example solution is doing:

```solidity
function setRewardsDuration(uint256 _rewardsDuration) external onlyRole(DEFAULT_ADMIN_ROLE) {
    uint256 periodFinish_ = periodFinish;
    if (block.timestamp < periodFinish_) {
        uint256 leftover = (periodFinish_ - block.timestamp) * rewardRate;
        rewardRate = leftover / _rewardsDuration;
        periodFinish = block.timestamp + _rewardsDuration;
    }

    rewardsDuration = _rewardsDuration;
    emit RewardsDurationUpdated(rewardsDuration);
}
```
