---
id: 25516
severity: "Low/Info"
---

# OstiumTrading::closeTradeMarket() Makes Redundant Call to OstiumTradingStorage::getOpenTradeInfo()

## Description

At [L284](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumTrading.sol#L284>) in OstiumTrading::closeTradeMarket(), the trade info can be reused from the previous call to OstiumTradingStorage::getOpenTradeInfo() at [L265](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumTrading.sol#L265>) to conserve gas by avoiding redundant function calls.

The same issue is seen in OstiumTrading::closeTradeMarketTimeout() on [L561](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L561>) and [L568](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L568>)

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
emit MarketCloseOrderInitiated( - orderId, storageT.getOpenTradeInfo(sender, pairIndex, index).tradeId,
```

sender, pairIndex + orderId, i.tradeId, sender, pairIndex );
