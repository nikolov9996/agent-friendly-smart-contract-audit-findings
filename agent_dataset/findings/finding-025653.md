---
id: 25653
severity: "Medium"
---

# FluidLocker::_getUnlockingPercentage() divides before multiplying, suffering a significant precision error

## Description



## Proof of Concept

Presented in the summary.

## Impact

User suffers a 1 BPS loss of funds. For example, 1e5 USD will yield a 10 USD loss.

## Recommendation

Multiply before dividing as it will never overflow.
