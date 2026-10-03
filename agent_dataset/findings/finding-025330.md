---
id: 25330
severity: "Low/Info"
---

# MapleLoan variables read from storage more than once.

## Description

In the MapleLoan contract, the following variables are loaded from storage multiple times:

- acceptNewTerms(): lender is loaded twice from storage.
- acceptNewTerms(): borrower is loaded from storage three times.
- makePayment(): lender is loaded from storage three times.

## Proof of Concept

No PoC provided.

## Recommendation

These variables should be loaded from storage just once and placed in temporary memory for later use (within the same function).
