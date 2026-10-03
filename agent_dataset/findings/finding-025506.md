---
id: 25506
severity: "Low/Info"
---

# Signer duplicate check can be performed by requiring signers being sent ordered

## Description

Signers are checked for duplicates by creating a memory signers array and looping through this array for every new signer, which is inefficient.

## Proof of Concept

No PoC provided.

## Recommendation

Cache the last signer and assert that the current signer is bigger than the last, require(signer > prevSigner, "duplicate". This is how Gnosis Safe does it, for example.
