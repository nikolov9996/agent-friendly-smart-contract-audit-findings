---
id: 25472
severity: "Low/Info"
---

# Total Position Size isn't updated properly

## Description

The totalPositionSize mapping is used to hold the position information for an amm using the TotalPositionSize struct, which has the following fields:

- int256 netPositionSize
- uint256 positionSizeLong
- uint256 positionSizeShort This mapping is updated exclusively through function _updateTotalPositionSize(...) of the [ClearingHouseBase](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouseBase.sol#L127-L139>) contract:

```solidity
function _updateTotalPositionSize(IAMM amm, int256 size, Side side) internal
{
    TotalPositionSize memory tps = totalPositionSize[amm];
    tps.netPositionSize += size;
    if (side == Side.LONG) {
        tps.positionSizeLong = size.abs() + tps.positionSizeLong;
    } else {
        tps.positionSizeShort = size.abs() + tps.positionSizeShort;
    }
    totalPositionSize[amm] = tps;
}
```

The issue in this function is that both tps.positionSizeLong and tps.positionSizeShort are being updated with the absolute value of the size, resulting in values that are always increasing and don't reflect the current size of all long/short positions.

For example, if someone opens a long position with a size of 1000 and then closes this position, the netPositionSize will go back to zero (as it should) but the positionSizeLong will go to 2000 (1000 on creation and 1000 on closure).

## Proof of Concept

No PoC provided.

## Recommendation

Change the _updateTotalPositionSize() function to increase/decrease the tps.positionSizeLong/tps.positionSizeShort variables depending on whether the size is positive or negative:

```solidity
if (side == Side.LONG) {
    tps.positionSizeLong = size > 0 ?
tps.positionSizeLong +
size.abs(): tps.positionSizeLong - size.abs();
} else {
tps.positionSizeShort = size < 0 ? tps.positionSizeShort +
size.abs(): tps.positionSizeShort - size.abs();
}
```

Tests for the totalPositionSize mapping should also be added.
