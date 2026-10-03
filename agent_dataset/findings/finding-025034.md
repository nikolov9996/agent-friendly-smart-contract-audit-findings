---
id: 25034
severity: "Low/Info"
---

# ManagedLeveragedVault::getDebtToUnwindAndCollRequested() is inaccurate when there are surplus tokens

## Description



## Proof of Concept

## Vulnerability Detail

`ManagedLeveragedVault::getDebtToUnwindAndCollRequested()` returns the debt to unwind and coll requested, but doesn't include the coll surplus as a view function offchain:

```solidity
function getDebtToUnwindAndCollRequested(uint256 _epoch) public view returns (uint256 debtToUnwind, uint256 collVaultSharesRequested, uint256 shareFee) {
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();
    ManagedLeveragedVaultStorage storage $ = _getManagedLeveragedVaultStorage();

    uint256 totalShares = $.reports[_epoch].totalShares;

    if (totalShares == 0) revert AmountZero();

    uint256 requestedAssets;
    (requestedAssets, shareFee) = _previewRedeem(totalShares);

    collVaultSharesRequested = _assetsToCollVaultShares(requestedAssets);

    (uint256 collVaultShares, uint256 debt) = IDenManager(b$.denManager).getDenCollAndDebt(address(this));

    // Find proportional debt unwind to collateral, so that ICR is unchanged, we assume an already pretty close ICR
    // If we were to responsabilize withdrawers to targetICR with a current deviated denICR, it would only responsabilize them to pay the slippage/borrow costs
    // Instead, we responsabilize both withdrawers and depositors, only using `increaseLeverage` and `decreaseLeverage`, which socializes losses
    debtToUnwind = debt * collVaultSharesRequested / collVaultShares; /// @dev Check `collVaultSharesRequested` can't be > `collVaultShares`
}
```

Essentially when it is called offchain `collVaultShares` doesn't include the surplus balance, but on chain it will always include it.

## Impact

View function is incorrect.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR787](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR787>)

## Recommendation

Include the surplus balance if it exists.
