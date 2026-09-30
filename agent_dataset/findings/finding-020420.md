---
id: 20420
severity: "Medium"
---

# Division difference can result in a revert

## Description

Different ordering of calculations are used to compute ysTotal in different situations. This causes the totalShares tracked to be less than the claimable amount of shares
ysTotal is calculated differently when adding to totalSuppliesTracking and when computing balanceOfYsCvgAt. When adding to totalSuppliesTracking, the calculation of ysTotal is as follows:
```solidity
uint256 cvgLockAmount = (amount * ysPercentage) / MAX_PERCENTAGE;
uint256 ysTotal = (lockDuration * cvgLockAmount) / MAX_LOCK;
```
In balanceOfYsCvgAt, ysTotal is calculated as follows
```solidity
uint256 ysTotal = (((endCycle - startCycle) * amount * ysPercentage) / MAX_PERCENTAGE) / MAX_LOCK;
```
This difference allows the balanceOfYsCvgAt to be greater than what is added to totalSuppliesTracking
This breaks the shares accounting of the treasury rewards. Some user's will get more than the actual intended rewards while the last withdrawals will result in a revert
totalSuppliesTracking calculation
cts/Locking/LockingPositionService.sol#L339-L345
In increaseLockTimeAndAmount
cvg/contracts/Locking/LockingPositionService.sol#L465-L470
_ysCvgCheckpoint
cvg/contracts/Locking/LockingPositionService.sol#L577-L584
balanceOfYsCvgAt calculation
cvg/contracts/Locking/LockingPositionService.sol#L673-L675

## Proof of Concept

startCycle 357
endCycle 420
lockDuration 63
amount 2
ysPercentage 80
Calculation in totalSuppliesTracking gives:
```solidity
uint256 cvgLockAmount = (2 * 80) / 100; == 1
uint256 ysTotal = (63 * 1) / 96; == 0
```
Calculation in balanceOfYsCvgAt gives:
```solidity
uint256 ysTotal = ((63 * 2 * 80) / 100) / 96; == 10080 / 100 / 96 == 1
```
Example Scenario
Alice, Bob and Jake locks cvg for 1 TDE and obtains rounded up balanceOfYsCvgAt. A user who is aware of this issue can exploit this issue further by using increaseLockAmount with small amount values by which the total difference difference b/w the user's calculated balanceOfYsCvgAt and the accounted amount in totalSuppliesTracking can be increased. Bob and Jake claims the reward at the end of reward cycle. When Alice attempts to claim rewards, it reverts since there is not enough reward to be sent.

## Recommendation

Perform the same calculation in both places
```solidity
uint256 _ysTotal = (_extension.endCycle -
_extension.cycleId)* ((_extension.cvgLocked *
_lockingPosition.ysPercentage) / MAX_PERCENTAGE) / MAX_LOCK;
```
```solidity
uint256 ysTotal = (((endCycle - startCycle) * amount *
ysPercentage) / MAX_PERCENTAGE) / MAX_LOCK;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an inconsistency in the way the contract computes the total amount of coverage shares (ysTotal) in two separate code paths. In the function that updates the global tracking of total supplies, the calculation multiplies the locked amount by the percentage, divides by the maximum percentage, and then multiplies the lock duration before dividing by the maximum lock period. In the view function that reports a user’s balance at a given cycle, the same variables are multiplied together first and then divided twice, effectively changing the order of integer division. Because Solidity performs integer division with truncation, the two formulas can produce different results when the intermediate product is not an exact multiple of the divisor. The result is that the balance reported by balanceOfYsCvgAt can be larger than the amount that was actually added to totalSuppliesTracking. This accounting mismatch allows a malicious user to lock a very small amount, obtain a rounded‑up balance from the view function, and later claim more rewards than the treasury has recorded. When the contract finally tries to distribute the rewards, the recorded total is insufficient and the transaction reverts, leaving the last claimant unable to withdraw. The issue manifests only when the arithmetic yields a fractional component – for example, with a lock duration of 63 cycles, an amount of 2 tokens and an 80 % percentage, the tracking calculation yields zero while the balance function yields one. Users see a normal reward balance in the UI, but the claim either succeeds with an unexpectedly high payout or fails with a revert, creating confusion and potential loss of funds. The bug was discovered during a manual audit by the researcher Sherlock, who exercised the functions with edge‑case values and observed the divergence. It is hard to notice because the discrepancy is hidden behind integer rounding and only appears with small amounts; the UI does not expose the internal totalSuppliesTracking value. The flaw belongs to the class of arithmetic precision or rounding bugs that break accounting invariants. To remediate the issue, the contract should use a single, canonical formula for ysTotal in all places, ensuring that multiplication and division are performed in the same order and that any rounding is applied consistently. Optionally, the code could employ a higher‑precision intermediate type or explicit rounding logic to guarantee that the reported balance never exceeds the tracked total, thereby preserving the integrity of the reward distribution mechanism.
