---
id: 25306
severity: "Low/Info"
---

# Factory update for maple loans can be performed with the old factory

## Description

In the [MapleLoanV502Migrator](<https://github.com/maple-labs/fixed-term-loan-private/blob/9effdcdc728b2ebcb659bc358fef76f86891b48a/contracts/MapleLoanV502Migrator.sol#L18>), the only check is that the factory address is a valid instance.

Thus, it's possible for a loan with the old factory to be updated and use the same old factory.

## Proof of Concept

No PoC provided.

## Recommendation

Prevent stale updates or hardcode the new factory address (via immutable variable in the constructor).
