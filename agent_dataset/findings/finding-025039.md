---
id: 25039
severity: "Medium"
---

# ManagedLeveragedVault::increaseLeverage() fails when the debt is closed to the limit

## Description



## Proof of Concept

## Vulnerability Detail

`ManagedLeveragedVault::increaseLeverage()` check is too strict requiring that the final ICR is very close to the target:

```solidity
_checkInvariantICR(getCurrentDenICR(), getTargetICR(), Tolerance.ABOVE);
```

Thus, it will not be possible to increase the leverage, even if this change would bring it closed to the target ICR.

## Impact

Smaller leverage than intended.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR449](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR449>)

## Recommendation

Allow the ICR to be higher than the target as long as it is above it.
