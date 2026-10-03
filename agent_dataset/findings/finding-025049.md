---
id: 25049
severity: "Medium"
---

# ManagedLeveragedVault::executeWithdrawalEpoch() will never work because cd.prevICR is not set

## Description



## Proof of Concept

## Vulnerability Detail

The last check in `ManagedLeveragedVault::executeWithdrawalEpoch()` is:

```solidity
_checkInvariantICR(getCurrentDenICR(), cd.prevICR, Tolerance.BOTH);
```

However, `cd.prevICR` is never set and it will always revert.

## Impact

DoSed withdrawals

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR393](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR393>)

## Recommendation

Set the old ICR.
