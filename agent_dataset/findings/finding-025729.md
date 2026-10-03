---
id: 25729
severity: "Low/Info"
---

# ClearingHouse::addEngine() initializes productEngine, so it may be frontrunned and someone initializes productEngine instead

## Description

ClearingHouse::addEngine() initializes productEngine, which means it is uninitialized prior to the call. Thus, someone may spot the uninitialized productEngine proxy and initialize it themselves, making the addEngine() call revert.

## Proof of Concept

No PoC provided.

## Recommendation

Send the productEngine creation and ClearingHouse::addEngine() atomically, via a multicall or custom contract deployer.
