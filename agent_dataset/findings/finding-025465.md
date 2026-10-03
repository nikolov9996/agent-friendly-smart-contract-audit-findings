---
id: 25465
severity: "Low/Info"
---

# Partially removing liquidity may underflow if the price of the pool has changed significantly

## Description

[removeLiquidity()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol#L654-L655>) updates the position quote and base amount based on the removed quote and base amounts.

However, if the proportions changed since the position was opened, it may underflow.

## Proof of Concept

No PoC provided.

## Recommendation

Reduce the quote and base amounts of the position pro-rata to the removed shares.
