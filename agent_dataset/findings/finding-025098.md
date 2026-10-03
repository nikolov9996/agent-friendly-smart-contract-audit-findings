---
id: 25098
severity: "Crit/High"
---

# PHyperLPoolSwapInside::_rebalance() checks the price manipulation before and after the swap with the same price threshold

## Description

[PHyperLPoolSwapInside::_rebalance()](<https://github.com/ClipFinance/StrategyRouter-private/pull/107/files#diff-023946f07f510e865612a28a9a222e00f0f6b90a253fd981e9bf4f7656f5497fR481>) checks price manipulation before swapping to prevent sandwich attacks and after swapping as a way to mitigate slippage.

The same priceThreshold is used for both checks, which means that when rebalancing a large amount in comparison to the pool's liquidity, which would lead to significant slippage, an equally large priceThreshold would need to be used.

This means that the PHyperLPoolSwapInside would be vulnerable to sandwich attacks.

## Proof of Concept

No PoC provided.

## Recommendation

Use 2 different priceTreshold variables, the first one smaller to guarantee that no sandwich attacks will happen and a second one, which could be bigger, to check slippage.
