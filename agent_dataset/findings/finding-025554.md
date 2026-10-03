---
id: 25554
severity: "Low/Info"
---

# OstiumTrading::canExecute() should also be checked in OstiumTradesUpKeep::checkCallback()

## Description

Orders in [OstiumTrading::executeAutomationOrder()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L468>) will not execute if they are in the timeout period.

This same check should exist in [OstiumTradesUpKeep::checkCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradesUpKeep.sol#L132-L136>) to ensure that non executable orders are added to tradesToTrigger.

## Proof of Concept

No PoC provided.

## Recommendation

Add the timeout check to OstiumTradesUpKeep::checkCallback().
