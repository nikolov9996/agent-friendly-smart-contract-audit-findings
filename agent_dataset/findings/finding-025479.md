---
id: 25479
severity: "Low/Info"
---

# Index underflow is not protected against, although it has no impact as the pool with index type(uint256).max should not be registered

## Description

The following places do an unchecked increment/decrement, but the index could underflow and become type(uint256).max. This has no consequences with the code as is, but it's better to revert for underflows. [https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L667](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L667>) [https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L1087-L1092](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L1087-L1092>) [https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/ClearingHouseBase.sol#L477](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/ClearingHouseBase.sol#L477>)

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
