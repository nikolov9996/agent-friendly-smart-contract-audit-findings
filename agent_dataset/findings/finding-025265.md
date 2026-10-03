---
id: 25265
severity: "Low/Info"
---

# Missing admin change events

## Description

When setting the admin in KeyringCoreV2Base::setAdmin() and the constructor an event should be emitted.

## Proof of Concept

No PoC provided.

## Recommendation

Emit events on all relevant state variable changes.
