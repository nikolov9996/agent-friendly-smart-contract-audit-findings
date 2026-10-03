---
id: 25549
severity: "Crit/High"
---

# In OstiumTradingStorage, firstEmptyTradeIndex() and firstEmptyOpenLimitIndex() overwrite index 0 if not found

## Description

[OstiumTradingStorage::firstEmptyTradeIndex()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingStorage.sol#L383>) and [OstiumTradingStorage::firstEmptyOpenLimitIndex()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingStorage.sol#L392>) return index 0 if they can not find an available index.

This may lead to overwriting a trade in storeTrade() if, for example, a trader has 2 trades, opens a third one via market order, but the Gov frontruns the chainlink bot OstiumPriceUpKeep() and sets _maxTradesPerPair to 2.

It will overwrite the trade in the [callback](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L132>), more specifically in [OstiumTradingCallbacks::registerTrade()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L427>) and lastly in [OstiumTradingStorage::storeTrade()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingStorage.sol#L146>).

## Proof of Concept

No PoC provided.

## Recommendation

Revert if it can not find an available open trade / limit order slot instead of returning index 0.
