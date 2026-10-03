---
id: 25097
severity: "Low/Info"
---

# PHyperLPoolSwapInside::_swapWithCustomData() checks price manipulation for pool, but the router used may route through another pool

## Description

[PHyperLPoolSwapInside::_swapWithCustomData()](<https://github.com/ClipFinance/StrategyRouter-private/pull/107/files#diff-023946f07f510e865612a28a9a222e00f0f6b90a253fd981e9bf4f7656f5497fR581>) checks price manipulation for pool; however, the router chosen may route through a different pool, rendering the price manipulation useless and leading to MEV.

## Proof of Concept

No PoC provided.

## Recommendation

Either enforce that the router used routes through the pool or do the price manipulation check for the pool that the router routed through.
