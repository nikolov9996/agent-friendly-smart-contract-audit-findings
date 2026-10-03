---
id: 25616
severity: "Low/Info"
---

# stakingAssetManager in ZKToken may be immutable as it is never changed

## Description

stakingAssetManager in ZKToken can be made immutable as it is set in the constructor and never changed.

## Proof of Concept

No PoC provided.

## Recommendation

Set stakingAssetManager to immutable to save gas on reads.
