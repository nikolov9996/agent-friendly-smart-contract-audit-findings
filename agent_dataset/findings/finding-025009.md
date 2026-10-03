---
id: 25009
severity: "Medium"
---

# Inconsistent Use of lastCumulativeRate in depositTokens() and withdraw() Functions in Borrowings Contract

## Description



## Proof of Concept

## Impact

The first transaction uses an outdated cumulative rate, while subsequent transactions use the updated cumulative rate, leading to incorrect interest calculations. This discrepancy causes inconsistencies in the normalized deposit amount and borrower debt, potentially affecting the protocol's financial accuracy .

## Recommendation

Ensure that `calculateCumulativeRate()` is called at the beginning of both the `depositTokens()` and `withdraw()` functions to update `lastCumulativeRate` before it is used in any calculations. This ensures that all transactions use the most current cumulative rate.
