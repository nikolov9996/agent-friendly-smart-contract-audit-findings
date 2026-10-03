---
id: 25422
severity: "Low/Info"
---

# RedeemQueue::isResolved() resolvedCount always returns requestIds.length

## Description

resolvedCount in RedeemQueue::isResolved() always increments in the loop, regardless of it being resolved_ or not. The function is not exposed so it has no impact but could be a future issue.

## Proof of Concept

No PoC provided.

## Recommendation

Only increment the count when it is resolved.
