---
id: 25346
severity: "Low/Info"
---

# open-term-loan-private: check dateFunded!=0 first to save gas.

## Description

On open-term-loan in function makePayment(), first the payment breakdown is called and after that the loan is checked to be active. getPaymentBreakdown() does several storage reads. dateFunded is not changed within the function scope, so the check if the loan is active (and the check for the principal as well) can be done before getPaymentBreakdown is called and save on gas from the storage reads in case the loan is inactive.

## Proof of Concept

No PoC provided.

## Recommendation

Change lines 173-178 to:

```solidity
require(dateFunded != 0, "ML:MP:LOAN_INACTIVE");
require(principalToReturn_ <= principal, "ML:MP:RETURNING_TOO_MUCH");
(calledPrincipal_, interest_, lateInterest_, delegateServiceFee_, platformServiceFee_) = getPaymentBreakdown(block.timestamp);

require(principalToReturn_ >= calledPrincipal_, "ML:MP:INSUFFICIENT_FOR_CALL");
```
