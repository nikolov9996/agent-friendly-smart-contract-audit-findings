---
id: 25471
severity: "Crit/High"
---

# reduceOnly limit order update does not take into account that a new amm may be selected, which may lead to loss of funds

## Description

On a limit order update, in [_updateLimitOrder()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/main/src/clearinghouse-libs/OrderCreator.sol#L293-L301>), changing amm is not being taken into account. The following scenarios are possible:

- if reduceOnly remains false, no problem
- if reduceOnly goes from false to true, no problem
- if reduceOnly remains true, it won't link the reduceOnly order in the new amm B, nor remove it from amm A
- if reduceOnly goes from true to false, it will remove the linked order from the new amm B, instead of the old amm A. This seems the worst scenario, as updating the limit order from false to true will pull weth from the trader, but this order may be [deleted](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/main/src/clearinghouse-libs/PositionManager.sol#L245>) if the trader closes its position on amm A, losing the funds.

## Proof of Concept

No PoC provided.

## Recommendation

Correctly handle the case when the amm changes.
