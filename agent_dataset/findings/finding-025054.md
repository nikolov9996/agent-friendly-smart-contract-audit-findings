---
id: 25054
severity: "Low/Info"
---

# Missing disableInitializers() call in StandardIDOPool::constructor()

## Description

The implementation contract `StandardIDOPool` can be initialized by an attacker, although it can not do anything with it.

## Proof of Concept

No PoC provided.

## Recommendation

Call `_disableInitializers()` in the constructor of `StandardIDOPool`.
