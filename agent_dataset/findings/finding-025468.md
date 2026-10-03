---
id: 25468
severity: "Medium"
---

# _getPriceToTick() reverts if the price is smaller than 1e10, which may happen in _search() as it assumes the final tick as going entirely to the amm

## Description

_search() calculates the final tick as if the order is completely filled on the amm. This means that if a significant chunk of the liquidity is in the limit orders, if a user has an order bigger than the current amm liquidity, it may return 1e7 from [amm.getMarkPriceAfterOpen()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol#L1170>), which reverts in [_getPriceToTick()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouseBase.sol#L490>), as it divides by 1e10 and reverts when [calculating](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/math/TickMath.sol#L63>) the tick.

## Proof of Concept

No PoC provided.

## Recommendation

Return 1e10 instead of 1e7 so that it does not round down to 0 in _getPriceToTick().
