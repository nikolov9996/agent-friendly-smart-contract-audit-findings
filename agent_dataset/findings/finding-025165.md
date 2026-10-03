---
id: 25165
severity: "Medium"
---

# rewardData.releaseRate is incorrectly calculated on RewardsController::config() when block.timestamp > start and rewardData.lastConfig != rewardData.start

## Description



## Proof of Concept

## Vulnerability Detail

When `RewardsController::config()` is called to update the data of a reward, as it was already set initially, it will go into the `else` branch. In here, it updates the `rewardRate` according to the previously distributed rewards, the total distribution and the distribution periods. More precisely, the calculation is:

```solidity
...
if (block.timestamp > start) {
  released =
    rewardData.lastConfigReleased +
    rewardData.releaseRate *
    (block.timestamp - rewardData.lastConfig);
  elapsed = block.timestamp - start;
  if (configs[i].totalDistribution <= released || configs[i].distributionPeriod <= elapsed) {
    revert InvalidConfig();
  }
  rewardData.lastConfigReleased = released;
}

rewardData.releaseRate =
  (configs[i].totalDistribution - released) /
  (configs[i].distributionPeriod - elapsed);
...
```

It calculates the release pro-rata to `block.timestamp - rewardData.lastConfig`, considering the time that the rewards have been emitted, but this is incorrect when `rewardData.start` was set in the future when creating the initial config. This will lead to the overestimation of released rewards, which will lower the `rewardData.releaseRate`, as it is pro-rata to `configs[i].totalDistribution - released`. Thus, less rewards will be distributed than expected.

## Impact

Lost of rewards for users that will receive less than supposed.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/RewardsController.sol#L681](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/RewardsController.sol#L681>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/RewardsController.sol#L699](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/RewardsController.sol#L699>)

## Recommendation

The release rewards are `rewardData.releaseRate * (block.timestamp - rewardData.start);`.
