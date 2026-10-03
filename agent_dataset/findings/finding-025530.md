---
id: 25530
severity: "Low/Info"
---

# Inconsistent Precision of Percentage Variables

## Description

Throughout the codebase, variables representing percentages maintain a precision of 2 decimal places. However, there are instances where this precision is not consistently applied:

- The MAX_GAIN_P variable on [L31](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingCallbacks.sol#L31>) in OstiumTradingCallbacks.
- The maxSl_P variable on [L47](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingCallbacks.sol#L47>) in OstiumTradingCallbacks.
- The liqThresholdP variable in OstiumPairInfos.
- The liqFeeP variable of the Fee struct in OstiumPairsStorage.

## Proof of Concept

No PoC provided.

## Recommendation

It is advisable to review the contracts and ensure that variables representing percentages consistently adhere to a precision of two decimal places.
