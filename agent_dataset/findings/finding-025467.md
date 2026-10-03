---
id: 25467
severity: "Low/Info"
---

# PriceFeed: First owner isn't set as valid keeper

## Description

When [changing contract owner](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/PriceFeed.sol#L129-L139>), the keeper permission of the previous owner is revoked, and this permission is given to the new owner.

The issue is that during initialization, the initial owner isn't given this privilege, so they must then call setValidKeeper() to set themselves (or some other address) as a valid keeper.

## Proof of Concept

No PoC provided.

## Recommendation

Since the owner should have the power to directly perform keeper operations, and for consistency with the function transferOwnership(), it is recommended that this permission is given during ownership initialization, [line 45](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/PriceFeed.sol#L45>).
