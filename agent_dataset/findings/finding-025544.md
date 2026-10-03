---
id: 25544
severity: "Low/Info"
---

# Redundant abi.decode() in OstiumTradesUpKeep::checkCallback()

## Description

The second decoding on [L126](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradesUpKeep.sol#L126>) of the data parameter is identical to the first and does not assign its result to any variable. This appears to be redundant and serves no discernible purpose.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the duplicate abi.decode() call.
