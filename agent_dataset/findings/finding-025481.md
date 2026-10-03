---
id: 25481
severity: "Low/Info"
---

# Call _updateMarkPrice() whenever markPrice is changed

## Description

Functions [addLiquidity()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L291>) and [removeLiquidity()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L350>) change mark price but don't call _updateMarkPrice().

Since these functions are meant to add/remove liquidity, the price isn't expected to fluctuate drastically, but numerical approximations and the use of virtual reserves can lead to some price fluctuation.

Calling _updateMarkPrice() would take a new snapshot of the price ensuring consistency between the markPrice variable and the snapshots on storage, as well as protect users in case of price fluctuation.

## Proof of Concept

No PoC provided.

## Recommendation

Call _updateMarkPrice() to update the markPrice instead of changing this variable directly
