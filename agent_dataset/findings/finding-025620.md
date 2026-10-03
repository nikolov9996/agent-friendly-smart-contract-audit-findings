---
id: 25620
severity: "Low/Info"
---

# StakingOperator::_setUnlockWindow() checks if the times are negative, which is impossible

## Description

In StakingOperator::_setUnlockWindow(), unlockWindowStart and unlockWindowDuration are uint256, so they can not be negative. However, the code checks for negative values, which is a waste of gas.

## Proof of Concept

No PoC provided.

## Recommendation

Replace both checks by equalities to 0.
