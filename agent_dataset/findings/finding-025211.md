---
id: 25211
severity: "Low/Info"
---

# Unnecessary extra condition in if statement

## Description

On the BorrowingVault.sol contract in the function _withdraw(...) the if statement checks the following conditions: if (totalDebt_ == 0 && supply > 0 && supply > totalDebt_) If the first two conditions are true the third will always be true, therefore there is no need to check it.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the third check in the if statement.
