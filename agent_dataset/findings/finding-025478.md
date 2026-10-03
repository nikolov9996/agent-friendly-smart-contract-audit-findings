---
id: 25478
severity: "Low/Info"
---

# gap is missing the private keyword

## Description

The abstract contracts use gaps to change storage later if required, but [AMMRouterBase](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouterBase.sol#L137>) is missing the private keyword.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
