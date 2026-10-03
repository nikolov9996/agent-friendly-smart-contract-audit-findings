---
id: 25476
severity: "Low/Info"
---

# Duplicate size to fill check in _staticFillToAmm()

## Description

[_staticFillToAmm()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/ClearingHouseBase.sol#L493-L495>) checks twice the size to fill.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the second check as it is never triggered.
