---
id: 25477
severity: "Low/Info"
---

# Use a flag to increase or decrease the index of the pool instead of a heuristic

## Description

[AmmRouter:_shitPool()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L757>) increases the index if the price is within 100 of the upper bound of the current pool price.

This is error prone as a fill could for example increase the price of a pool, but not be close enough to the upper bound, making the index decrease, entering in a wrong state.

## Proof of Concept

No PoC provided.

## Recommendation

Use the direction flag to increase or decrease the index, as in [AmmRouter:_getQuoteValue()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L809>).
