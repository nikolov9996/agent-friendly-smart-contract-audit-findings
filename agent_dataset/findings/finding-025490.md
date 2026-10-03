---
id: 25490
severity: "Low/Info"
---

# The number of underlying tokens may be modified in the Vault leading to inconsistent exchange rate

## Description

The price is calculated based on the ratio from managedRatiosOracle.getTargetRatiosX96(). Currently the vault has only 1 underlying token, which means the ratio will always be 1e18.

However, the vault may add more tokens, which would change this.

## Proof of Concept

No PoC provided.

## Recommendation

Clarify the behaviour if more tokens are added.
