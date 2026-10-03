---
id: 25594
severity: "Low/Info"
---

# Curve pools should be whitelisted as some of them may not be 100% compatible

## Description

Curve pools vary significantly between one another, which could lead to unexpected behavior. For example, it may be possible to add liquidity to a certain curve pool, but not remove it, due to incompatibilities, leading to lost funds.

## Proof of Concept

No PoC provided.

## Recommendation

Whitelist curve pools that have been tested to work.
