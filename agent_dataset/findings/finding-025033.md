---
id: 25033
severity: "Low/Info"
---

# ManagedLeveragedVault::getAvailableDebt() used in ManagedLeveragedVault::increaseLeverage() is incorrect

## Description



## Proof of Concept

## Vulnerability Detail

This is the `ManagedLeveragedVault::getAvailableDebt()` function:

```solidity
function getAvailableDebt() internal view returns (uint256) {
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();

    IDenManager denManager = IDenManager(b$.denManager);

    uint256 borrowCap = denManager.maxSystemDebt();
    uint256 totalActiveDebt = denManager.getTotalActiveDebt();
    uint256 defaultedDebt = denManager.defaultedDebt();

    return borrowCap - totalActiveDebt - defaultedDebt;
}
```

It doesn't account for the borrowing fee triggered, which means the max debt will be overestimated.

## Impact

This function would be used most likely offchain to calculate the max debt to leverage up, which would revert.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR428](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR428>)

## Recommendation

This function should return the debt multiplied by (1 - borrowingFee).
