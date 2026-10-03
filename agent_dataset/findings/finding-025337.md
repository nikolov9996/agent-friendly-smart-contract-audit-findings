---
id: 25337
severity: "Low/Info"
---

# MapleLoan, proposeNewTerms() could have a check for duplicate selectors.

## Description

Terms can be proposed with duplicated calls, which could lead to mistakes or phishing attacks.

## Proof of Concept

No PoC provided.

## Recommendation

Send the calls ordered by selector and check that the next selector is strictly bigger than the previous.
