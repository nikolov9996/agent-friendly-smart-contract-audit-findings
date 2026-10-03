---
id: 25319
severity: "Low/Info"
---

# Missing documentation for MapleLoan, SetPendingLender and AcceptLender being implemented on MapleLoan but not on LoanManager.

## Description

Fixed and Open term loans implement SetPendingLender and AcceptLender; however, the corresponding LoanManagers don't. This is a design choice to allow a future upgrade of LoanManager without the necessity of upgrading MapleLoan.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
