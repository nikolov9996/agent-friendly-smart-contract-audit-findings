---
id: 25553
severity: "Low/Info"
---

# OstiumTradesUpKeep Triggers Automation for Pending Orders Expected to Fail

## Description

In [OstiumTradesUpKeep::_getOpenOrdersToTrigger()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradesUpKeep.sol#L316>), orders are grouped together for execution without some important checks.

This means that some orders that should be triggered can fail due to checks in OstiumTrading::executeAutomationOrder() or in the execution functions of OstiumTradingCallbacks.

For example, when fetching trades for liquidation in OstiumTradesUpKeep::_getOpenOrdersToTrigger(), there's no check to see if the trade has a stop loss.

This means these orders won't execute because of [this](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L454>) check in the OstiumTrading::executeAutomationOrder().

Note: this check should also be added to [OstiumTradingCallbacks::executeAutomationCloseOrderCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L347>).

Also, checks for market closure, max allowed leverage per pair and the pause status of the OstiumTradingCallbacks contract, are missing in [OstiumTradesUpKeep::_getLimitOrdersToTrigger()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradesUpKeep.sol#L190>), which means that these orders will fail inside the OstiumTradingCallbacks::executeAutomationOpenOrderCallback().

## Proof of Concept

No PoC provided.

## Recommendation

Review the checks in OstiumTrading::executeAutomationOrder() and the execution functions of OstiumTradingCallbacks, and make sure similar checks are added to the functions responsible for fetching orders in OstiumTradesUpKeep. This ensures that only orders likely to succeed are triggered, saving gas.
