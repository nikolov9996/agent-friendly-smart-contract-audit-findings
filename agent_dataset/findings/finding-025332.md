---
id: 25332
severity: "Low/Info"
---

# LoanManager code optimizations: no need to load payment struct from storage if loan is unimpaired.

## Description

In the LoanManager contract, two changes can be made to reduce gas usage and improve readability: In function _accountForLoanImpairmentRemoval(): loading the payment struct from storage should only be performed after the check to see if the loan is impaired, since the vast majority of the time, a payment will be made to an unimpaired loan, so there is no need to load this struct from storage as it will not be used.

This change would result in a makePayment() call cheaper by around 3000 gas. An identical issue can be found in function _accountForLoanImpairment().

## Proof of Concept

No PoC provided.

## Recommendation

Only load the payment struct from storage after the line which returns if the loan is impaired.
