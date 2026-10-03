---
id: 25412
severity: "Low/Info"
---

# Linea does not support PUSH0

## Description

Linea does not support PUSH0, so it may be necessary to compile the contracts with an old em version (such as Paris, which is the one currently used).

## Proof of Concept

No PoC provided.

## Recommendation

Keep in mind that the contracts will not work on Linea as is if the evm version picked is shanghai or more recent.
