---
id: 25452
severity: "Low/Info"
---

# New debt from adjusted trove is double counted towards the limit

## Description



## Proof of Concept

## Vulnerability Detail

`BorrowerOperations::_moveTokensFromAdjustment()` checks if the debt has exceeded the limit by requiring that `troveManager.getDebtLimit() >= troveManager.getEntireSystemDebt() + _troveChange.debtIncrease`. However, when this check is performed, `troveManager.getEntireSystemDebt()` already includes the `_troveChange.debtIncrease` component, as it was added previously in the `vars.activePool.mintAggInterestAndAccountForTroveChange(_troveChange, batchManager);` call.

## Impact

Adjusting troves will revert due to the debt limit when they should not.

## Code Snippet

[https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/BorrowerOperations.sol#L670](<https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/BorrowerOperations.sol#L670>) [https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/BorrowerOperations.sol#L1227](<https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/BorrowerOperations.sol#L1227>)

[https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/ActivePool.sol#L164](<https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/ActivePool.sol#L164>) [https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/ActivePool.sol#L233-L238](<https://github.com/sherlock-audit/2025-02-nerite/blob/main/nerite/contracts/src/ActivePool.sol#L233-L238>)

## Recommendation

`require(troveManager.getDebtLimit() >= troveManager.getEntireSystemDebt(), "BorrowerOperations: Debt limit exceeded.");` should be enough.
