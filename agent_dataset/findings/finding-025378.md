---
id: 25378
severity: "Low/Info"
---

# _setDefaultRoyalty() in the constructor is overriding the BasicRoyalties constructor

## Description

_setDefaultRoyalty() in the [constructor](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L53>) is overriding the BasicRoyalties constructor to 500, regardless of the parameter sent.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
