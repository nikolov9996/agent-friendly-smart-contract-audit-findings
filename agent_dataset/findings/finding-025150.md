---
id: 25150
severity: "Medium"
---

# Some bad debt will not be cleared when it should which will cause accrual of bad debt decreasing the protocol's solvency

## Description



## Proof of Concept

The following code snippet can be verified to confirm the issue:

```solidity
function clearBadDebt(address borrower) external {
  {
    {
      ...
      if (accumulator >= badDebt) {
        ...
        if (fixedPools[maturity].borrowed == position.principal) {
          earningsAccumulator += fixedPools[maturity].unassignedEarnings;
          fixedPools[maturity].unassignedEarnings = 0;
        }
        ...
      }
    }
  }
  ...
}
```

## Recommendation

Increase the earnings accumulator first and only then compare it against the bad debt.
