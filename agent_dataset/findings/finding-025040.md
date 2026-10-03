---
id: 25040
severity: "Low/Info"
---

# ManagedLeveragedVault::increaseLeverage() will never work in Recovery mode

## Description



## Proof of Concept

## Vulnerability Detail

`ManagedLeveragedVault::increaseLeverage()` withdraws debt:

```solidity
b$.borrowerOperations.withdrawDebt(
    b$.denManager,
    address(this),
    _maxFeePercentage,
    _debtAmount,
    _upperHint,
    _lowerHint
);
```

But this is not possible in Recovery mode, as it requires that the new ICR is bigger than the old one.

## Impact

DoSed increasing leverage.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR431-R438](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR431-R438>)

## Recommendation

Nothing can be really done but it's something to keep in mind.
