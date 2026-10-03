---
id: 25043
severity: "Low/Info"
---

# Most ManagedLeveragedVault functions are DoSed due to bad debt check

## Description



## Proof of Concept

## Vulnerability Detail

`ManagedLeveragedVault:: _assetsValuation()` reverts when there is bad debt:

```solidity
if (debtValue > collateralValue + exposureValue) {
    revert BadDebt(debtValue - (collateralValue + exposureValue));
}
```

This will make all ERC4626 functions revert that must not do so when called, becoming non compliant. Additionally, it is not possible to request withdrawal intents temporarily.

## Impact

DoSed request intent and non ERC4626 compliance

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR985](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR985>)

## Recommendation

Handle the situation instead of reverting to allow the normal behaviour of the mentioned functions (although the behaviour may be hard to define).
