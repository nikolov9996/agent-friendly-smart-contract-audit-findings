---
id: 25285
severity: "Low/Info"
---

# Inconsistent naming of function in PureEpochs

## Description

The [PureEpochs](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/libs/PureEpochs.sol>) library implements a variety of functions centered on the definition of epochs.

For example, it includes the following functions:

- getTimeSinceEpochStart
- getTimeSinceEpochEnd
- getTimeUntilEpochStart It also includes the function getTimeUntilEpochEnds. The naming of this function in particular is inconsistent with the remaining ones.

## Proof of Concept

No PoC provided.

## Recommendation

Change the name of the getTimeUntilEpochEnds function to getTimeUntilEpochEnd.
