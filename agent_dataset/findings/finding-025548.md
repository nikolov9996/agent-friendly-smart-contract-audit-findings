---
id: 25548
severity: "Low/Info"
---

# .values() may revert when calling getWatchList() due to OOG

## Description

If the number of registries in the [s_registries](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/dev/src/OstiumLinkUpKeep.sol#L207>) set grows too large, it will revert when calling [getWatchList()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/dev/src/OstiumLinkUpKeep.sol#L206>) due to OOG.

## Proof of Concept

No PoC provided.

## Recommendation

Add a paginated function to get the watch list.
