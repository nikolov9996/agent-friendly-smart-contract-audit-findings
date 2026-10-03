---
id: 25512
severity: "Low/Info"
---

# executeAutomationOpenOrderCallback Executes STOP Orders at a Worse Price

## Description

The condition executed when the OpenOrderType is of type STOP, as seen [here](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingCallbacks.sol#L274>), triggers when the current price is greater than or equal to the target price.

This approach results in traders potentially receiving a worse price compared to using price after impact >= target price. This is because when buying, the price typically rises, meaning that the target price may be reached sooner than when using the current market price.

## Proof of Concept

No PoC provided.

## Recommendation

Use: cancelReason = ( o.orderType == IOstiumTradingStorage.OpenOrderType.LIMIT ? (o.buy ? priceAfterImpact > o.targetPrice : priceAfterImpact < o.targetPrice)

- : (o.buy ? uint192(a.price) < o.targetPrice : uint192(a.price) > o.targetPrice) + : (o.buy ? priceAfterImpact < o.targetPrice : priceAfterImpact > o.targetPrice) )
