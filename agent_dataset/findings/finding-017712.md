---
id: 17712
severity: "High"
---

# isValidRefinance will approve invalid refinances

## Description

The math in isValidRefinance() checks whether the rate increased rather than decreased, resulting in invalid refinances being approved and valid refinances being rejected. When trying to buy out a lien from LienToken.sol:buyoutLien(), the function calls AstariaRouter.sol:isValidRefinance() to check whether the refi terms are valid.
```solidity
if (!ASTARIA_ROUTER.isValidRefinance(lienData[lienId], ld)) {
    revert InvalidRefinance();
}
```
One of the roles of this function is to check whether the rate decreased by more than 0.5%. From the docs: An improvement in terms is considered if either of these conditions is met:  
• The loan interest rate decrease by more than 0.5%.  
• The loan duration increases by more than 14 days.  
The current implementation of the function does the opposite. It calculates a minNewRate (which should be maxNewRate) and then checks whether the new rate is greater than that value.
```solidity
uint256 minNewRate = uint256(lien.rate) - minInterestBPS;
return (newLien.rate >= minNewRate ...
```
The result is that if the new rate has increased (or decreased by less than 0.5%), it will be considered valid, but if it has decreased by more than 0.5% (the ideal behavior) it will be rejected as invalid.  
• Users can perform invalid refinances with the wrong parameters.  
• Users who should be able to perform refinances at better rates will not be able to.

## Proof of Concept

no poc

## Recommendation

Flip the logic used to check the rate to the following:
```solidity
uint256 maxNewRate = uint256(lien.rate) - minInterestBPS;
return (newLien.rate <= maxNewRate...
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the refinance validation routine of the Astaria protocol. The function isValidRefinance is intended to enforce business rules that consider a refinance improvement only when the new loan interest rate is at least 0.5% lower than the current rate or when the loan duration is extended by more than 14 days. However, the implementation mistakenly calculates a minimum acceptable new rate (named minNewRate) and then checks that the proposed rate is greater than or equal to this value. In effect, the logic is inverted: a higher or insufficiently lower rate is treated as valid, while a genuinely better rate that drops more than 0.5% is rejected. This reversal stems from using the wrong variable name (minNewRate instead of maxNewRate) and an incorrect comparison operator (>= instead of <=). When a borrower calls LienToken.buyoutLien, the router invokes isValidRefinance; the faulty check allows a refinance transaction with a worse interest rate to pass the validation step, and simultaneously blocks legitimate refinances that would lower the rate. An attacker could exploit this by submitting a refinance request with a higher interest rate, causing the protocol to accept a financially disadvantageous loan for the borrower. Conversely, honest users attempting to improve their loan terms experience a revert with the InvalidRefinance error, seeing no improvement despite providing correct parameters. The impact includes potential loss of value for borrowers, erosion of trust in the protocol’s refinancing feature, and distortion of the intended economic incentives. The bug manifests whenever the refinance validation is performed, i.e., during any buyoutLien call that supplies new loan terms. It affects all participants who rely on the refinance mechanism – borrowers, lenders, and the protocol itself. The issue was uncovered during a security audit by Sherlock, who compared the documented business rules with the actual Solidity code and identified the contradictory condition. Because the function name suggests a correctness check, the error can be subtle and may not be caught by superficial testing; only edge‑case tests that verify the direction of rate change would expose it. To remediate, the logic must be flipped: compute a maximum allowable new rate as the current rate minus the minimum interest basis points (maxNewRate = lien.rate - minInterestBPS) and ensure the new rate is less than or equal to this threshold (newLien.rate <= maxNewRate). Renaming the variable and adding explicit comments would also reduce future confusion. From a user’s perspective, the symptom is a mismatch between expectation (“I should get a lower rate”) and reality (“the transaction reverts” or “the rate stays the same or gets higher”). This class of bug is a business‑logic validation error where a financial constraint is enforced with an inverted conditional, leading to incorrect approval of undesirable loan terms.
