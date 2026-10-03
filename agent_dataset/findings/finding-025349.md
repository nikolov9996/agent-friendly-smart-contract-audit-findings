---
id: 25349
severity: "Medium"
---

# Open term loans can be created with zero platform service fee if borrowers create them right after a pool has been deployed.

## Description

The platform service fee is set on loan deployment; however, when a pool is deployed, its platform service fee is 0 (has not been set yet), so a borrower could deploy a loan right after a pool deployment and have 0 platform service fee.

## Proof of Concept

No PoC provided.

## Recommendation

Set the platformServiceFee when a loan is [funded instead](<https://github.com/maple-labs/three-sigma-audit-2023-04-10/issues/29>) of when created, similarly to what happens on the fixed term loan.
