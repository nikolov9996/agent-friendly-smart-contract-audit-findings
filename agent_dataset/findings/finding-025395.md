---
id: 25395
severity: "Low/Info"
---

# emissionStart has no effect, rewards will start accumulating starting on the first staker

## Description

emissionStart is set in the constructor, but it has no use other than summing with the emissionDuration to set the emissionEnd. Rewards will be accrued as long as block.timestamp is before emissionEnd and totalStakedAccruingRewards is non null.

## Proof of Concept

No PoC provided.

## Recommendation

Either remove this variable or change the logic to accumulate rewards only after emission starts.
