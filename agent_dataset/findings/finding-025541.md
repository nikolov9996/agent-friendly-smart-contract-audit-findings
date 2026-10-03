---
id: 25541
severity: "Medium"
---

# Missing Pausability Check in OstiumTrading::executeAutomationOrder() for Opening Orders

## Description

The [execution](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L437>) of a limit order within the OstiumTrading::executeAutomationOrder() function lacks a check to determine if the contract is paused.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
if (orderType == IOstiumTradingStorage.LimitOrder.OPEN) {
    if (!storageT.hasOpenLimitOrder(trader, pairIndex, index)) {
        return IOstiumTrading.AutomationOrderStatus.NO_LIMIT;
    }
+
isNotPaused();
IOstiumTradingStorage.OpenLimitOrder memory l = storageT.getOpenLimitOrder(trader, pairIndex, index);
leveragedPos = l.collateral * l.leverage / 100;
}
```
