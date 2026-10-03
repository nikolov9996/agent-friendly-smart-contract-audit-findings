---
id: 25475
severity: "Low/Info"
---

# Add a 0 address check on the pool when adding liquidity for greater verbosity

## Description

[AmmRouter:addLiquidity()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L283>) does not have an explicit check regarding the existence of the pool with the given id, making it only revert when calling poolsAdded[i].addLiquidity() due to internal EVM checks.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
