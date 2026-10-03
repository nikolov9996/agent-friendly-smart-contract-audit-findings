---
id: 25495
severity: "Low/Info"
---

# BRC20Factory and Vault do different checks when removing signers

## Description

BRC20Factory checks if the account is authorized and if its index stored in indexes[account] is smaller than the length of signers. Vault requires that the length of signers is bigger than 1 and the account is authorized.

## Proof of Concept

No PoC provided.

## Recommendation

The check that the index of the account is smaller than the length of signers is not required and can be removed. Also, decide if it makes sense to check if the length of the signers is bigger than 1 in the BRC20Factory or if this check is not required in both contracts.
