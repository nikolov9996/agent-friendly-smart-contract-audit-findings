---
id: 25517
severity: "Medium"
---

# OstiumTrading::closeTradeMarket() and OstiumTrading::topUpCollateral() are missing pending trigger checks

## Description

[OstiumTrading::closeTradeMarket()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L250>) and [OstiumTrading::topUpCollateral()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L388>) can be used to frontrun liquidation calls whose trigger has already been set, making the liquidation fail in OstiumPriceUpKeep::performUpkeep(), draining fees and gaming the system.

## Proof of Concept

No PoC provided.

## Recommendation

Add [OstiumTrading::checkNoPendingTrigger()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L578>) to both functions.
