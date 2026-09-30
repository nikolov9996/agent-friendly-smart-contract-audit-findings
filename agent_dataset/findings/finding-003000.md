---
id: 3000
severity: "High"
---

# RefinanceController._validateRefinance() allows the new principal to be greater than the active balance of the old loan.

## Description

RefinanceController._validateRefinance() does the following check for the new loan's principal:
```solidity
// principal cannot increase
if (newTerms.principal > oldLoanData.terms.principal) revert REFI_PrincipalIncrease(
    oldLoanData.terms.principal,
    newTerms.principal
);
```
This check, however, does not account for any previous partial repayments made towards the old loan. Therefore, it allows for refinancing loans where the new loan will have a higher principal than the active balance of the old loan.
The problem is that when the new loan's principal amount is more than the old loan's unrepaid amount (i.e. newPrincipalAmount > oldLoanData.balance), the borrower doesn't receive his repayment back.
For example:
- Assume that an old loan's principal is 100 USDC, and the borrower has repaid 50 USDC so far.
- For simple calculations, we assume that all fees are 0%, and that the old loan has no interest to repay.
- If we rollover into a new loan with principal as 90 USDC, the numbers in rolloverAmounts() will be:
  oldLoanPrincipal = 50
  oldInterestAmount = 0
  newPrincipalAmount = 90
  borrowerOwedForNewLoan = newPrincipalAmount = 90
  amountFromLender = newPrincipalAmount = 90
  repayAmount = oldPrincipal + oldInterestAmount = 50
- Since repayAmount > borrowerOwedForNewLoan, the logic takes the else branch that repays funds to the borrower:
  amountToBorrower = borrowerOwedForNewLoan - repayAmount = 40
After the calculations in rolloverAmounts(), the result is amountToBorrower = 40, which means the borrower should receive 40 USDC from refinanceLoan(). However, LoanCore.rollover() is called with amountToBorrower specified as 0:
```solidity
amounts.amountToOldLender,
0,
0, // amountToBorrower
```
So the borrower doesn't get his 40 USDC back. The accounting for the borrower is:
- He received 100 USDC for the old loan's principal.
- He repaid 50 USDC.
- After the loan is refinanced, he owes 90 USDC to the new lender.
Therefore, he is at a net loss of 100 - 50 - 90 = 40 USDC.

## Proof of Concept

no poc

## Recommendation

Restrict the new loan's principal to the old loan's unrepaid amount:
```solidity
// principal cannot increase
if (newTerms.principal > oldLoanData.balance) revert REFI_PrincipalIncrease(
    oldLoanData.terms.principal,
    newTerms.principal
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the refinance validation logic of the loan protocol. The function that checks whether a new loan can be created during a refinance only compares the new loan's principal amount with the original principal of the old loan. It does not take into account any partial repayments that the borrower may have already made, so the check permits a new loan whose principal is larger than the outstanding balance of the old loan. When this situation occurs, the internal accounting that calculates how much should be returned to the borrower (amountToBorrower) computes a positive value, but the subsequent call to the rollover function deliberately passes zero for that field, effectively withholding the funds that the borrower is entitled to receive. As a result, a borrower who has repaid part of the original loan expects to get the excess repayment back after refinancing, but receives nothing, leading to a net loss equal to the difference between the repaid amount and the new principal. The bug manifests only when a loan has been partially repaid before a refinance is initiated, and it affects any borrower who attempts such a refinance as well as the lenders who rely on correct accounting. The issue was discovered during a manual audit by Renascence, who noticed that the validation condition ignored the loan's current balance and that the rollover call set the borrower‑return amount to zero. The problem is subtle because the validation appears to enforce a sensible rule (principal cannot increase) and the missing repayment is hidden inside an internal function call, making it easy to overlook during testing. Conceptually, the flaw belongs to the class of accounting or business‑logic validation errors where state‑dependent constraints are not fully enforced. To remediate the issue, the validation should compare the new principal against the old loan's outstanding balance rather than the original principal, and the rollover logic should forward the correctly calculated amountToBorrower so that borrowers receive any excess repayment they are owed. This change restores the intended financial invariants and prevents borrowers from losing funds during a refinance operation.
