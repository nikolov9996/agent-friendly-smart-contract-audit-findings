---
id: 25500
severity: "Low/Info"
---

# Checks effects interactions pattern is now always followed

## Description

State changes should always be performed before interacting with an external contract, or it increases the risk of reentrancy attacks.

## Proof of Concept

No PoC provided.

## Recommendation

In Vault::withdraw() decrease allowances[token] before sending the funds. In Vault::withdrawFees() set totalFees to 0 before transferring the funds.
