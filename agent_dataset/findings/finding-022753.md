---
id: 22753
severity: "High"
---

# liquidateDefaultedLoanWithIncentive can be abused to avoid interest payment

## Description

The amountDue calculation at the liquidateDefaultLoanWithIncentive function at the LenderCommitmentGroup contract calls getAmountOwedForBid with a false argument, which means it considers the principal lent as owed but not the interest that was accrued during the borrow period. This can be gamed by malicious users to avoid paying loans interest. Take a look at the getAmountOwedForBid function:
```solidity
function getAmountOwedForBid(uint256 _bidId, bool _includeInterest)
    public
    view
    virtual
    returns (uint256 amountOwed_)
{
    Payment memory amountOwedPayment = ITellerV2(TELLER_V2).getAmountOwedForBid(_bidId, _includeInterest);
    amountOwed_ = _includeInterest
        ? amountOwedPayment.principal + amountOwedPayment.interest
        : amountOwedPayment.principal;
}
```
Notice it will only return the principal amount if a false boolean is passed as the second argument of a call to it. At the liquidateDefaultedLoanWithIncentive function, this is exactly what happens:
```solidity
function liquidateDefaultedLoanWithIncentive(
    uint256 _bidId,
    int256 _tokenAmountDifference
) public bidIsActiveForGroup(_bidId) {
    uint256 amountDue = getAmountOwedForBid(_bidId, false);
    ...
}
```
This means the amountDue does not include interest. However, this is not on par with TellerV2 contract, as its liquidation function does repay both the owed principal and the interest. This can be seen at the following code snippet:
```solidity
function _liquidateLoanFull(uint256 _bidId, address _recipient)
    internal
    acceptedLoan(_bidId, "liquidateLoan")
{
    ...
    _repayLoan(
        _bidId,
        Payment({ principal: owedPrincipal, interest: interest }),
        owedPrincipal + interest,
        false
    );
    ...
}
```
Users can arbitrarily decide to liquidate repaying interest or not back to Teller lenders by liquidating via the TellerV2 contract or via LenderCommitmentGroups contracts. LenderCommitmentGroups's liquidation function spreads bad debt to the whole lending pool while benefitting the liquidator.

## Proof of Concept

no poc

## Recommendation

Ensure the calculation of amountDue accounts for interest when repaying a liquidated bid. The following change could be done at the code:
```solidity
uint256 amountDue = getAmountOwedForBid(_bidId, true);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting omission in the liquidation routine of the LenderCommitmentGroup contract. When a defaulted loan is liquidated through the function liquidateDefaultedLoanWithIncentive, the contract calculates the amount that must be repaid by calling getAmountOwedForBid with the boolean flag set to false. This flag tells the helper function to return only the principal component of the debt and to ignore any interest that accrued during the borrowing period. The root cause is a logical error: the developer passed the wrong argument, causing the liquidation logic to treat the loan as if only the principal were owed. An attacker can exploit this by triggering liquidation on a defaulted loan, paying back only the principal, and receiving the liquidation incentive while the accrued interest remains unpaid. Because the TellerV2 contract’s own liquidation path requires repayment of both principal and interest, the discrepancy allows the liquidator to shift the unpaid interest to the rest of the lending pool, effectively spreading bad debt among all lenders. The exploit works whenever a loan is in default and the liquidator calls liquidateDefaultedLoanWithIncentance; no additional conditions are required. The parties affected are borrowers (who avoid interest), liquidators (who profit from the incentive and the interest shortfall), and lenders (who lose the expected interest revenue and see the pool balance shrink). The issue was discovered during a manual audit that inspected the call to getAmountOwedForBid and noticed the false argument, a detail that can be easy to miss because the function still repays the principal and the transaction appears successful. The impact is a financial loss to the lending pool, distortion of interest accounting, and erosion of confidence in the protocol’s fairness. To remediate, the amountDue calculation must include accrued interest, for example by invoking getAmountOwedForBid with true, or by otherwise ensuring that the liquidation routine repays both principal and interest consistently with the TellerV2 contract. This class of bug is a typical under‑payment or interest‑exclusion error in loan settlement logic. From a user’s perspective, a lender may notice that after a liquidation the expected interest payout is missing or that the pool balance drops unexpectedly, while a borrower may see that no interest is charged after liquidation, contrary to the protocol’s business rules that liquidations should settle the full debt.
