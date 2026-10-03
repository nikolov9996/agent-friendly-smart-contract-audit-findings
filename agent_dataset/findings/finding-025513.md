---
id: 25513
severity: "Low/Info"
---

# OstiumTradingCallbacks::executeAutomationOpenOrderCallback() opens limit orders at market price instead of the limit price

## Description

Limit orders usually trade at the specified price; however, [OstiumTradingCallbacks::executeAutomationOpenOrderCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L290>) registers the limit order t.openPrice at priceAfterImpact, which would be different than the specified.

For example, a limit order at price 5000 will be opened when the price after impact is below it, for example 4950, and the trade will have an open price of 4950, not 5000 as the limit price specified.

This is more profitable for the user as it's buying cheaper, but most likely not the intended behaviour.

## Proof of Concept

No PoC provided.

## Recommendation

If the o.orderType == IOstiumTradingStorage.OpenOrderType.LIMIT, the open price should be o.targetPrice. If o.orderType == IOstiumTradingStorage.OpenOrderType.STOP, the open price should be priceAfterImpact.

Note that this would change the [negative pnl](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L280>) of the trade so that should also be adjusted.
