---
id: 25496
severity: "Low/Info"
---

# BRC20Factory constructor is missing a duplicate check

## Description

BRC20Factory constructor does not check for duplicate signers, which would lead to problems as the index would be overriden.

## Proof of Concept

No PoC provided.

## Recommendation

Check for duplicate signers using the recommendation from #4.
