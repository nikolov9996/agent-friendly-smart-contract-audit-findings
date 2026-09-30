---
id: 22759
severity: "High"
---

# User can bypass copay and get 100% coverage

## Description

```solidity
Users can open a "Cost Share Request" (CSR) using the FairSideClaim contract's
openPWPRequest. The function checks that the account has purchased enough cost
share benefits for the claim amount requested. However, the cross share benefit
is checked against claim amount after taking a 10 percent haircut. Therefore a user
can request availableCostShareBenefits * 10/9 to pass the check and get 100
percent coverage.
The following are the relevant snippets for the issue:
• Cost share requests are opened using the openPWPRequest function.
• requestPayout is returned after haircutting 10% of claimAmount in validateCSR
• The CostShareRequest takes the returned requestPayout as the claimAmount
(what will be paid)
uint256 private constant NON_USA = 0.9 ether;
function openPWPRequest(uint256 claimAmount, uint256 coverId, bool inETH)
external payable onlyCoverIdOwner(coverId) {
    (uint256 requestPayout, uint256 availableCostShareBenefits) =
    validateCSR(claimAmount, coverId);
    createCostshareRequest(requestPayout, claimAmount, 0, coverId);
}

function validateCSR(uint256 claimAmount, uint256 coverId) private view
returns (uint256, uint256) {
    Membership memory account = fairSideNetwork.getMembership(coverId);
    // 90% of the full claim is paid out as 10% in the USA
    uint256 requestPayout = claimAmount.mul(NON_USA);
    if (account.availableCostShareBenefits < requestPayout) {
        revert FSClaims_CostRequestExceedsAvailableCostShareBenefits();
    }
    return (requestPayout, account.availableCostShareBenefits);
}

function createCostshareRequest(uint256 requestPayout, uint256 claimAmount,
uint256 _csrType, uint256 coverId) private {
    CostShareRequest memory csr = CostShareRequest(
        uint80(block.timestamp),
        msg.sender,
        coverId,
        _csrType,
        requestPayout,
        bytes32(0),
        ClaimStatus.IN_PROGRESS
    );
    costShareRequests[nextClaimId] = csr;
}
```
As seen above, requestPayout is 90% of the claimAmount:
```solidity
uint256 requestPayout = claimAmount.mul(NON_USA);
```
Then the requestPayout is checked against the member's cost share benefits:
```solidity
if (account.availableCostShareBenefits < requestPayout) {
    revert FSClaims_CostRequestExceedsAvailableCostShareBenefits();
}
```
Therefore if the user passes a claimAmount that after 10% haircut will be equal to
availableCostShareBenefits and pass the if statement, then requestPayout will be
equal to the entire cost share benefit. User will receive 100% coverage.
The amount of claimAmount needed is availableCostShareBenefits * 10/9.
For example, if user purchased 90 ETH cost share benefits: 90 ether * 10/9 = 100
ether.
Supplying 100 ether as claimAmount will bypass the user copay.
Loss of funds. 100% coverage instead of expected 90%

## Proof of Concept

no poc

## Recommendation

Consider changing the if statement to check against claimAmount instead:
```solidity
if (account.availableCostShareBenefits < claimAmount) {
    revert FSClaims_CostRequestExceedsAvailableCostShareBenefits();
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an incorrect validation of a user’s cost‑share entitlement in the FairSideClaim contract. When a user opens a Cost Share Request via openPWPRequest, the contract calculates a payout amount (requestPayout) by applying a 10 % haircut to the submitted claimAmount (requestPayout = claimAmount * 0.9). The subsequent check compares the user’s availableCostShareBenefits against this reduced requestPayout instead of the original claimAmount. Because the check uses the already‑discounted value, an attacker can inflate the claimAmount to exactly availableCostShareBenefits * 10/9. After the 0.9 multiplication, requestPayout equals the full available benefit balance, the if‑statement passes, and the contract records a cost‑share request for the entire benefit amount. This allows the user to bypass the intended 10 % copay and receive 100 % coverage, resulting in a loss of funds for the protocol. The issue occurs whenever a cover holder calls openPWPRequest with a claimAmount that satisfies the described relationship; no additional constraints are required. Affected parties include any cover holder able to submit claims, the protocol’s treasury that funds the payouts, and downstream insurers that rely on the correct risk‑sharing model. The flaw was discovered during a manual audit of the claim‑processing logic, where the auditor noticed that the validation step used the haircut‑adjusted amount rather than the original claim amount, a subtle arithmetic mismatch that can be easily overlooked because the 10 % haircut is a legitimate business rule elsewhere in the code. The bug belongs to the class of financial‑logic errors where validation is performed on a transformed value rather than the original, leading to mismatched accounting units. From a user’s perspective the UI may display a full refund where a partial reimbursement (with a 10 % user contribution) was expected, violating the business rule that only 90 % of a claim should be covered by the protocol. The attack flow is: (1) attacker reads their availableCostShareBenefits B; (2) computes inflated claimAmount = B * 10/9; (3) calls openPWPRequest with this claimAmount; (4) validateCSR multiplies by 0.9, producing requestPayout = B; (5) the if‑statement passes because B <= B; (6) createCostshareRequest records a request for B, which is later paid out, draining the protocol of the full benefit amount. The recommended fix is to compare the user’s available benefits against the original claimAmount (or otherwise ensure that the same value is used consistently in both the haircut calculation and the eligibility check), thereby preventing the copay bypass.
