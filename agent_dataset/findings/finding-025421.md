---
id: 25421
severity: "Medium"
---

# RedeemQueue::getAvailableResolveRange() incorrectly returns false if from == count - 1

## Description

RedeemQueue::getAvailableResolveRange() returns the indices to resolve a requestor, but returns nothing if from == count - 1. For example, this would return when from == 0 and count == 1 (there's 1 element), when it should not.

This could be problematic if a user only has 1 request and the redeem queue is disabled, it would never be able to claim until the redeem queue is enabled again.

## Proof of Concept

No PoC provided.

## Recommendation

Return if from == count. The check if (count == 0) return (0, 0, false); is also not required, as it is covered by the other check.
