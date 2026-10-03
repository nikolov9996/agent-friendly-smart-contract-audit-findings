---
id: 25522
severity: "Low/Info"
---

# In OstiumLinkUpKeep, empty watchlist or keeperIds arguments are not handled

## Description

In OstiumLinkUpKeep, functions [setWatchList()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/dev/src/OstiumLinkUpKeep.sol#L131>), [addToWatchList()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/dev/src/OstiumLinkUpKeep.sol#L142>) and [removeFromWatchList()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/dev/src/OstiumLinkUpKeep.sol#L153>) don't handle 0 length array inputs, which could lead to incorrect state.

## Proof of Concept

No PoC provided.

## Recommendation

Explicitly check for empty arrays.
