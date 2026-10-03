---
id: 25480
severity: "Low/Info"
---

# In AmmRouter:liquidateMaker(), the pools array can safely be deleted from storage

## Description

AmmRouter:liquidateMaker() calls [_unregisterPoolsFromMaker()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L411>) with all the pools, which means that it could simply delete the pools from storage.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
