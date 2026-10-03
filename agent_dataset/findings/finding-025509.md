---
id: 25509
severity: "Low/Info"
---

# OstiumTrading::executeAutomationOrder() and _getLimitOrdersToTrigger() should check isPaused for open limit orders

## Description

OstiumTrading::openTrade() correctly checks isPaused to not allow opening positions when the protocol is paused. However, [executeAutomationOrder()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L420>) still allows execution if it is an open limit order, which it should not, as it will fail when [OstiumPriceUpKeep()::performUpKeep()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPriceUpKeep.sol#L103>) executes.

Moreover, it will not discount oracle fees if it is paused or the market has been closed.

## Proof of Concept

No PoC provided.

## Recommendation

Check if OstiumTradingCallbacks is paused in OstiumTradingUpKeep() and in OstiumTrading::executeAutomationOrder() for open limit orders.
