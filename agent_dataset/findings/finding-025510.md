---
id: 25510
severity: "Low/Info"
---

# OstiumOpenPnl::average() can be simplified by adding a state variable that tracks the cumulative sum of nextEpochValues

## Description

[OstiumOpenPnl::average()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumOpenPnl.sol#L187>) calculates the average of all the nextEpochValues, which is an expensive operation (depending on requestsCount and could be replaced by a state variable tracking the cummulative sum.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
