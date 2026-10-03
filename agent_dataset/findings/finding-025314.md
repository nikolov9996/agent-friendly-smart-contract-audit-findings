---
id: 25314
severity: "Medium"
---

# DoS attack if assets are transferred before a fundLoan() call.

## Description

In fixed term loans, a DoS attack is possible if assets are transferred into the MapleLoan before the loan is funded. Exploit scenario

- delegate funds loan
- attacker frontruns delegate and transfers fundsAsset to the MapleLoan
- funding reverts due to the require that the unaccounted funds are 0

## Proof of Concept

No PoC provided.

## Recommendation

Skim before funding.
