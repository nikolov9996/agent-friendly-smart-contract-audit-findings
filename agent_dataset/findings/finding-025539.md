---
id: 25539
severity: "Medium"
---

# Error in OstiumPairsStorage::groupMaxCollateral() calculation

## Description

The [calculation](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumPairsStorage.sol#L234>) of the maximum deposited collateral per group, erroneously divides by 100, assuming it refers to 100%.

However, the maxCollateralP variable, specified [here](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/interfaces/IOstiumPairsStorage.sol#L21>), has a precision of 2 decimals.

This means that 100% is expressed as 100_00. This discrepancy results in [incorrect checks](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingCallbacks.sol#L513>) in OstiumTradingCallbacks::withinExposureLimits(), potentially causing the vault's collateral to be capped at a much larger amount than intended.

Furthermore, this miscalculation may dilute the reported profits.

## Proof of Concept

No PoC provided.

## Recommendation

To avoid errors related to magic numbers, utilize constants for precision. Additionally, if using 100_00 to denote 100% consistently, it's preferable to adhere to Basis Point (BPS) denomination.
