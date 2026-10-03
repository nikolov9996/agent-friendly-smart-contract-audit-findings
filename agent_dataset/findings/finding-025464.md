---
id: 25464
severity: "Low/Info"
---

# getTriggerOrders() should be paginated or it may revert if enough orders are created

## Description

There is no limit in the amount of triggerOrders, which means that the array may grow too large and make transactions revert due to the gas usage exceeding the block gas limit when calling [getTriggerOrders()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/main/src/ClearingHouse.sol#L753>).

## Proof of Concept

No PoC provided.

## Recommendation

Paginate the getter so users can fetch information safely.
