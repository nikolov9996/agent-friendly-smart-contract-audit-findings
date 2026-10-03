---
id: 25523
severity: "Low/Info"
---

# OstiumOpenPnl::nextEpochValuesRequestCount stores the same information as nextEpochValues.length

## Description

[OstiumOpenPnl::nextEpochValuesRequestCount](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumOpenPnl.sol#L29>) can be removed as it is the same as checking [nextEpochValues.length](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumOpenPnl.sol#L24>).

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
