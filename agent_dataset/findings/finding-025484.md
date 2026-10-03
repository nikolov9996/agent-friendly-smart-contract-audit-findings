---
id: 25484
severity: "Medium"
---

# Notional difference in AmmRouter:removeLiquidty() may revert in certain cases

## Description

[AmmRouter:removeLiquidity()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L367-L371>) subtracts the long notional by the short notional if the size is bigger than 0 (contrary if size is smaller than 0), which may revert if the short notional is bigger than the long one.

## Proof of Concept

No PoC provided.

## Recommendation

Use the distance between the notionals.
