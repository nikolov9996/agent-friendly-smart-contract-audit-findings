---
id: 25485
severity: "Medium"
---

# Price deviation as is can be circumvented by making smaller trades in a loop

## Description

The price deviation [check](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouterBase.sol#L290>) will look at the last price snapshots; however, it does not actually enforce that these are from past blocks.

Thus, attackers may split a trade in smaller trades and incrementally increase the price.

## Proof of Concept

No PoC provided.

## Recommendation

Store the price of the previous block.
