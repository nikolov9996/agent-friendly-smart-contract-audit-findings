---
id: 25398
severity: "Low/Info"
---

# Variables should be cached to memory to save gas

## Description

Storage reads are expensive and should be avoided. This is usually done by caching storage variables in memory ones.

## Proof of Concept

No PoC provided.

## Recommendation

Replace all storage rewards that happen more than once per function (or even better, per flow) for memory caching. Example:

```solidity
function rewardPerToken() public view returns (uint256) {
    uint256 totalStakedAccruingRewardsCached = totalStakedAccruingRewards;
    if (totalStakedAccruingRewardsCached == 0) {
        return rewardPerTokenStored;
    }
    return rewardPerTokenStored + (
```

(lastApplicableTime() - lastUpdateTime) * rewardRate * 1e18 / totalStakedAccruingRewardsCached

```solidity
);
}
```
