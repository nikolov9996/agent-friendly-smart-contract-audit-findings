---
id: 25435
severity: "Low/Info"
---

# LoopStrategy::totalAssets() tracks the wFlow balance, but this is not redeemable

## Description

The LoopStrategy is not supposed to hold wFlow directly, but this is still tracked in totalAssets(). However, this is not redeemed in _withdraw(), so it will be stuck.

## Proof of Concept

No PoC provided.

## Recommendation

Consider withdrawing wFlow on _withdraw() or remove the balance from the totalAssets() calculation.
