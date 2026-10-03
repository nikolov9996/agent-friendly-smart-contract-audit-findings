---
id: 25555
severity: "Low/Info"
---

# OstiumTrading::updateOpenLimitOrder() Makes Unnecessary Field Updates

## Description

In OstiumTrading::updateOpenLimitOrder(), unnecessary fields of the OpenLimitOrder struct are updated. Specifically, the createdAt field is set, despite its intended immutability after creation, and the lastUpdated field is also updated.

Subsequently, this object is passed to OstiumTradingStorage::updateOpenLimitOrder(), where lastUpdated is reassigned to the current block. However, the createdAt field remains unaltered as intended.

## Proof of Concept

No PoC provided.

## Recommendation

Do the following changes in OstiumTrading::updateOpenLimitOrder():

```solidity
- uint32 b = ChainUtils.getBlockNumber().toUint32();
o.targetPrice = price;
o.tp = tp;
o.sl = sl;
- o.createdAt = b;
- o.lastUpdated = b;
```
