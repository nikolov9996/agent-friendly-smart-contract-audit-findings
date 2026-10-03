---
id: 25411
severity: "Low/Info"
---

# Initializable constracts should call _disableInitializers() in the constructor instead of using the initializer modifier

## Description

When locking the implementation contract, the usual behaviour is calling _disableInitializers().

## Proof of Concept

No PoC provided.

## Recommendation

For better readability, consider calling _disableInitializers() instead of placing the initializer modifier in the constructor.
