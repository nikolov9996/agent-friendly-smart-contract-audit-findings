---
id: 25458
severity: "Low/Info"
---

# In fillPair(), when the taker is the maker, the reduceOnly order mapping is not being deleted

## Description

When filling limit orders, if the trader doing the openPosition() call is the same as the maker of the limit order, it will [delete](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/clearinghouse-libs/PositionManager.sol#L524>) the limit order.

## Proof of Concept

No PoC provided.

## Recommendation

If the limit order is a reduceOnly order, it should also delete the [reduceOnlyOrders](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouseBase.sol#L91>) mapping.
