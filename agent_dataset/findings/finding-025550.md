---
id: 25550
severity: "Low/Info"
---

# Unused Trade Size Variable in OstiumTrading::executeAutomationOrder()

## Description

The leveragedPos variable in OstiumTrading::executeAutomationOrder() is calculated on [L443](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L443>) and [L465](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L465>), but its value isn't utilized anywhere in the function.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
