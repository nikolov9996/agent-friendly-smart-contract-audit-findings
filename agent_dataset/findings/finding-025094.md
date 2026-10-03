---
id: 25094
severity: "Low/Info"
---

# Missing _disableInitializers() call in the constructor

## Description

PCLBaseSwapInside() is missing a _disableInitializers() call in the constructor, allowing the implementation contract to be initialized. This is not a security concern at the moment but could be in a future version of the implementation.

## Proof of Concept

No PoC provided.

## Recommendation

Add _disableInitializers() to the constructor.
