---
id: 25518
severity: "Medium"
---

# OstiumTrading::topUpCollateral() is missing pairsStored.groupMaxCollateral(pairIndex) check

## Description

When opening trades it is checked if the collateral is within limits for each pair in [OstiumTradingCallbacks::withinExposureLimits()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L513>).

The same should be done in [OstiumTrading::topUpCollateral()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L388>).

## Proof of Concept

No PoC provided.

## Recommendation

Add the check to OstiumTrading::topUpCollateral().
