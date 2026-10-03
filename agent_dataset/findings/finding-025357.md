---
id: 25357
severity: "Low/Info"
---

# MapleSkyStrategy does not always cache the psm and misses underscores

## Description

MapleSkyStrategy::_gemForUsds() and MapleSkyStrategy::_usdsForGem() do not cache the psm nor add trailing underscores to tout and to18ConversionFactor.

## Proof of Concept

No PoC provided.

## Recommendation

Implement the fixes to ensure gas savings and correct formats.
