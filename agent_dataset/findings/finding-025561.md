---
id: 25561
severity: "Low/Info"
---

# OstiumLinkUpKeep:removeFromWatchList() complexity could be reduced

## Description

[OstiumLinkUpKeep:removeFromWatchList()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/dev/src/OstiumLinkUpKeep.sol#L163>) currently iterates over the full s_registryWatchLists to find the keeperIds and delete them if equal. This has O(n^2) complexity, which could cost a significant amount of gas.

## Proof of Concept

No PoC provided.

## Recommendation

One way to tackle this problem is tweaking the isInWatchList mapping to store the index of the array instead of a bool, adding 1 to each index so that 0 is not a valid index and can be used to check for abcense. This way, when removing, the index can be fetchd from the corresponding mapping.
