---
id: 25024
severity: "Crit/High"
---

# Potential Underflow in withdrawInterest

## Description



## Proof of Concept

1. Set `totalInterest` to 50 and `totalInterestFromLiquidation` to 100.
2. Attempt to withdraw an `amount` of 75.
3. The `require` passes because 75 ≤ 150.
4. Subtracting 75 from `totalInterest` (50) causes an underflow and reverts.

## Recommendation

Implement logic to deduct the `amount` from `totalInterest` and `totalInterestFromLiquidation` proportionally or sequentially:

```solidity
if (amount <= totalInterest) {
    totalInterest -= amount;
} else {
    uint256 remaining = amount - totalInterest;
    totalInterest = 0;
    totalInterestFromLiquidation -= remaining;
}
```
