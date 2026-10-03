---
id: 25397
severity: "Low/Info"
---

# Missing some events

## Description

Events in the constructor are not emitted. rewardPerToken update could emit an event. withdrawFees() is missing feesAccrued event. completeUnstake() is missing fee paid event.

## Proof of Concept

No PoC provided.

## Recommendation

Emit events for all state changes.
