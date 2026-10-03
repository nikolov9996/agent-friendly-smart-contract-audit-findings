---
id: 25177
severity: "Low/Info"
---

# _checkNoBalanceChange(...) cycle should break in BaseRouter

## Description

_checkNoBalanceChange(...) has a for cycle that goes through all tokens. For each token it checks if they are address(0), this is only true if we have arrived at the end of the list of tokens, therefore we can break the cycle to save on gas.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
