---
id: 25487
severity: "Low/Info"
---

# setPools() could use more validation

## Description

AmmRouter:setPools() is an admin function but could still benefit from input validaiton to prevent mistakes. For example, specifying a pool id that already [exists](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L183>) will overwrite the current amm, which could be dangerous.

Additionally, it should be checked that the bounds of the pools increase with the index, which is currently not enforced but the logic depends on it.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
