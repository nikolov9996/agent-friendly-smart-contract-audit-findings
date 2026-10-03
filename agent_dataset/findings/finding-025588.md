---
id: 25588
severity: "Low/Info"
---

# BaseAssetManager missing 0 address checks in the constructor

## Description

0 address checks in the constructor are a safety check to ensure addresses are correctly set. The BaseAssetManager, which is inherited by all pool managers, could perform these checks.

## Proof of Concept

No PoC provided.

## Recommendation

Place these checks in the BaseAssetManager.
