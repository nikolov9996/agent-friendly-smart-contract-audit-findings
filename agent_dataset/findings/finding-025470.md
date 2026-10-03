---
id: 25470
severity: "Crit/High"
---

# Realized pnl not returned to trader on _mergeDecrease()

## Description

On the merge of a liquidator position following a liquidation, the [realizedPnl](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/clearinghouse-libs/PositionMerger.sol#L516>) from the previous position is not added to the marginToRemove() variable, but it is [removed](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/clearinghouse-libs/PositionMerger.sol#L526-L530>) from the openNotional, leading to loss of yield for the liquidator.

## Proof of Concept

No PoC provided.

## Recommendation

Add the = symbol to the operation marginToRemove += params.rpnl;.
