---
id: 25482
severity: "Low/Info"
---

# _match() always checks the trigger of the first order of a certain tick, instead of checking i order

## Description

[PositionManager:_match()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/clearinghouse-libs/PositionManager.sol#L398>) looks for all the orders for their trigger values as some order may have been filled/deleted.

However, currently it only checks the first order instead of the i one, which could cause problems down the line.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
