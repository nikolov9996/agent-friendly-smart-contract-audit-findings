---
id: 9960
severity: "High"
---

# Reducing the quantity of a policyholder results in an increase instead of a decrease in totalQuan- tity

## Description

In Llama policyholder can approve or disapprove actions. Each policyholder has a quantity which represents their approval casting power. It is possible to update the quantity of individual policyholder with the setRoleHolder function in the LlamaPolicy. The _setRoleHolder method is not handling the decrease of quantity correctly for the totalQuantity. The totalQuantity describes the sum of the quantities of the individual policyholders for a specific role. In the case of a quantity change, the difference is calculated as follows:
```solidity
uint128 quantityDiff = initialQuantity > quantity ? initialQuantity - quantity : quantity - initialQuantity;
```
However, the quantityDiff is always added instead of being subtracted when the quantity is reduced. This results in an incorrect tracking of the totalQuantity. Adding the quantityDiff should only happen in the increase case.

## Proof of Concept

no poc

## Recommendation

The increase and decrease case of quantity should be handled in separate if-conditions or using an int variable for calculating the difference. Decrease:
```solidity
if(hadRoleQuantity && willHaveRole && initialQuantity > quantity) {
    newTotalQuantity = currentRoleSupply.totalQuantity - quantityDiff;
}
```
Increase:
```solidity
if(hadRoleQuantity && willHaveRole && initialQuantity < quantity) {
    newTotalQuantity = currentRoleSupply.totalQuantity + quantityDiff;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting logic error in the LlamaPolicy contract where the function that updates a policyholder's quantity calculates the difference between the old and new quantity as an unsigned value and then always adds this difference to the stored totalQuantity, even when the new quantity is lower. Because the code uses a uint128 quantityDiff and a single addition operation, the sign of the change is lost. When a role holder's quantity is reduced, the contract mistakenly increases the aggregate totalQuantity, inflating the voting power associated with that role. This can be exploited by an attacker who holds a role and calls setRoleHolder with a smaller quantity, causing the contract to record a larger totalQuantity than actually exists. The inflated totalQuantity may allow the attacker to meet quorum thresholds or pass proposals with fewer genuine approvals, compromising the governance of the protocol and potentially leading to unauthorized fund movements. The bug manifests only when the quantity is decreased; increasing the quantity works correctly because the same addition matches the intended effect. Users observing the UI may see that after lowering a holder's weight, the displayed total weight for the role either stays the same or grows, contradicting the expectation that it should drop. The issue was discovered during a manual audit that inspected the _setRoleHolder logic and noticed that the same addition is used for both increase and decrease paths. It is hard to notice because the contract does not revert or emit an error; the totalQuantity simply diverges from the real sum, and the discrepancy may be small enough to escape casual testing. The bug belongs to the class of aggregation or accounting bugs where signed changes are treated as unsigned and always added, leading to incorrect state accumulation. To fix the problem the code should handle increase and decrease cases separately, or compute a signed difference (int) and apply it with addition or subtraction accordingly, ensuring that a reduction in quantity subtracts the difference from totalQuantity. Proper validation and tests that assert totalQuantity equals the sum of individual quantities after any change would prevent the regression.
