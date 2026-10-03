---
id: 25466
severity: "Low/Info"
---

# Swapping amounts that would send the price below/above the bounds of the amm underflows without a reason

## Description

For example, [_getBaseValue()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol#L1348>) calculates the base amount according to the k using the virtual reserves; however, some amounts will return a base amount bigger than the real reserves, silently underflowing when updating the reserves in [swapOpen()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol#L344>).

## Proof of Concept

No PoC provided.

## Recommendation

Add a revert message if the base/quote amount calculated is bigger than the real base/quote reserves.
