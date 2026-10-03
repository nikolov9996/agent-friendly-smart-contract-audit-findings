---
id: 25463
severity: "Low/Info"
---

# _getPositionNotional() crops the size of the position to the available reserves, which may lead to unexpected profits/losses

## Description

[_getPositionNotional()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouseBase.sol#L425>) fills positions to the amm if it can't find limit orders.

However, if the remaining size of the position is bigger than the available base reserves in the AMM, it crops the size of the position (for short positions), decreasing the current notional.

It does not seem possible to exploit this situation, as some tests were carried out which led to big losses, but the position could not be closed as there was not enough liquidity, nor could it be liquidated as liquidations use the liquidation price and the not the current value of the position.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if there is not enough liquidity to make sure the value of the position is correctly calculated.
