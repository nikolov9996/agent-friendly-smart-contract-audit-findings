---
id: 25545
severity: "Low/Info"
---

# Redundant Calculations in OstiumTrading::openTrade()

## Description

When opening a LIMIT or STOP order, the first empty index is calculated using OstiumTradingStorage::firstEmptyOpenLimitIndex() on [L209](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L209>).

However, the same function is executed again in OstiumTradingStorage::storeOpenLimitOrder() on [L233](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingStorage.sol#L233>), which results in the index property being overridden with the same value.

Similarly, the current block number is retrieved on [L211](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L211>) in OstiumTrading, and then on [L231](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingStorage.sol#L231>) in OstiumTradingStorage.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the redundant overriding of these variables from OstiumTradingStorage::storeOpenLimitOrder().
