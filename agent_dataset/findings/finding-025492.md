---
id: 25492
severity: "Low/Info"
---

# Token addresses are not validated in BRC20Factory and Vault, so users can use incorrect tokens

## Description

BRC20Factory::mint(), BRC20Factory::burn(), Vault::deposit() and Vault::withdraw() allow sending any token, which could lead to problems if the token is not a BRC20.

## Proof of Concept

No PoC provided.

## Recommendation

Validate the sent token was created by the factory. To do this an isBRC20 mapping should be added to BRC20Factory which stores all the tokens that were created by it.
