---
id: 25326
severity: "Low/Info"
---

# In MapleLoanInitializer, the Borrower can choose a different fundsAsset than the lender.

## Description

The code allows for the Borrower to choose a different fundsAsset than the lender. At the moment this will make fund() revert and the borrower has to redeploy the loan with the right argument, however this results in a lot of wasted gas and could even become a bigger problem in a future upgrade.

## Proof of Concept

No PoC provided.

## Recommendation

Add a check in the MapleLoanInitializer to make sure the loan's asset matches that of the loan manager's.
