---
id: 25389
severity: "Low/Info"
---

# renounceOwnership() should be disabled if it is not intended to be ever used

## Description

Calling renounceOwnership() would block the owner from very important functions, which would be problematic. When this is the case and the owner is not supposed to be renounced in the future, it's best to disable the renounceOwnership() function.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
