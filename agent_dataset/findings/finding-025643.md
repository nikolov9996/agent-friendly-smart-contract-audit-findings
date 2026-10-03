---
id: 25643
severity: "Crit/High"
---

# FluidLocker::_getUnlockingPercentage() uses 540 instead of 540 days leading to stuck funds as the unlocking percentage will be bigger than 100% and underflow

## Description



## Proof of Concept

The calculation is presented in the summary. Essentially, as `540` is used in the denominator, much smaller than the correct `540 days` (which is the maximum unlock period, when the percentage becomes `100%`), the value will be much bigger than `10_000`.

As the unlocking percentage is bigger than `10_000`, the unlock flow rate

```solidity
unlockFlowRate = (globalFlowRate * int256(_getUnlockingPercentage(unlockPeriod))).toInt96()
            / int256(_BP_DENOMINATOR).toInt96();
```

will be bigger than the global flow rate, so it reverts when calculating the tax flow rate `taxFlowRate = globalFlowRate - unlockFlowRate;`.

## Impact

User is forced to take a `80%` penalty or have the funds stuck.

## Recommendation

Use `540 days` instead of `540`.
