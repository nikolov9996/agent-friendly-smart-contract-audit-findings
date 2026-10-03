---
id: 25534
severity: "Crit/High"
---

# Liquidations can be prevented by updating the SL timeout before it expires

## Description

Traders who continually [update](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairInfos.sol#L421>) their [stop losses](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L454-L456>) before the SL timeout expires will never face liquidation.

This is because liquidating via a LimitOrder of type LIQ is impossible when the limit order includes a stop loss. Additionally, triggering the stop loss with a LimitOrder of type SL is hindered by the [timeout check](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L468>).

A PoC can be found [here](<https://github.com/0xOstium/smart-contracts-threeSigma/commit/a39b9ffea1d95a39ac361e18f31903f0f3fc66f6>).

## Proof of Concept

No PoC provided.

## Recommendation

If the trade is liquidatable, disregard the timeout for stop losses.
