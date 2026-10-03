---
id: 25462
severity: "Low/Info"
---

# mul() and div() in NFTPMath are misleading due to scaling by 1e18 underneath

## Description

Usually mul() and div() do multiplication and division, respectively, without scaling by 1e18 (commonly used by SafeMath). However, NFTPMath [`mul()`](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/math/NFTPMath.sol#L22>) and [`div()`](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/math/NFTPMath.sol#L26>) scale the operations by 1e18, misleading code readers.

For example, when looking at ClearingHouse:openPosition(), it seems that it would round down to 0 in [`_assertMaxLeverage()`](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouse.sol#L776>), but this is not the case as it correctly scales the numbers.

## Proof of Concept

No PoC provided.

## Recommendation

Consider renaming the functions to fullMulWad() and fullDivWad().
