---
id: 25547
severity: "Low/Info"
---

# reqID_pendingAutomationOrder stores the index of the trade, which could point to a different trade since the request was created

## Description

reqID_pendingAutomationOrder store the trader, pairIndex and index. index points to the trade in OstiumTradingStorage::openTrades, but the trade itself may have changed since the OstiumPriceUpKeep automation was requested.

A possible scenario is, for example, triggering a take profit, then closing the trade immediately and creating a new trade on index 0 before the first callback was triggered. Note: this is also true for open limit orders, it should also check if the a.orderId matches the corresponding limit order.

The easiest way to fix this is adding a orderId field to OpenLimitOrder which is filled when OstiumTrading::executeAutomationOrder() [requests](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L470>) a price.

## Proof of Concept

No PoC provided.

## Recommendation

To avoid this problem, [OstiumTradingCallbacks::executeAutomationCloseOrderCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L319>) and [OstiumTradingCallbacks::closeTradeMarketCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L191>) should validate a.orderId against [OstiumTradingStorage::openTradesInfo.tradeId](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingStorage.sol#L39>).
