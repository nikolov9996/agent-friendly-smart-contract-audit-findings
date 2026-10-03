---
id: 25050
severity: "Medium"
---

# ManagedLeveragedVault::executeWithdrawalEpoch() incorrect ICR and DoSed withdrawals due to not accouting for fees

## Description



## Proof of Concept

## Vulnerability Detail

`ManagedLeveragedVault::executeWithdrawalEpoch()` repays and withdraws:

```solidity
function executeWithdrawalEpoch(
    ExecuteWithdrawalParams calldata params
) external onlyOwner nonReentrant claimCollateralSurplus(params.upperHint, params.lowerHint) {
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();

    _checkEpoch(params.epoch);

    CollDebt memory cd = _getCollVaultSharesAndDebtToUnwind(params.epoch);

    b$.borrowerOperations.adjustDen({
        denManager: b$.denManager,
        account: address(this),
        _maxFeePercentage: params.maxFeePercentage,
        _collDeposit: 0,
        _collWithdrawal: cd.collVaultSharesToWithdraw,
        _debtChange: cd.debtToUnwind,
        _isDebtIncrease: false,
        _upperHint: params.upperHint,
        _lowerHint: params.lowerHint
    });
    ...
}
```

The math is supposed to keep the ICR just the same as before the withdrawal, which is attempted in `getDebtToUnwindAndCollRequested()`:

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

However, after this debt is calculated to have the exact ICR ratio as before, the shares withdrawn will be further reduced by the slippage loss when getting the debt (NECT) from the exposure token:

```solidity
function getCollVaultSharesToWithdraw(uint256 _collVaultSharesRequested, uint256 _debtToUnwind, uint256 _exposureWithdrawn) public view returns (uint) {
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();

    address collVault = address(b$.collVault);

    // Instead of recalculating totalAssets, which socializes the loss to everyone
    // Let's see how much the loss was, and apply it to the withdrawer by substracting the collVaultShares to withdraw
    uint256 exposureWithdrawnValue = _getExposureValue(_exposureWithdrawn);
    /// @dev Most cases will present a loss, but in case of profit, we don't add coll
    uint256 slippageLossInUsd = exposureWithdrawnValue > _debtToUnwind ? exposureWithdrawnValue - _debtToUnwind : 0;
    uint256 slippageLossInColl = slippageLossInUsd.convertToColl(getPrice(collVault), IAsset(collVault).decimals(), Math.Rounding.Up);
    return _collVaultSharesRequested - slippageLossInColl;
}
```

Thus, the final ICR will be incorrect and the withdrawal may be DoSed due to this `_checkInvariantICR(getCurrentDenICR(), cd.prevICR, Tolerance.BOTH);`.

## Impact

DoSed withdrawals.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR819](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR819>)

## Recommendation

The debt to repay in `getDebtToUnwindAndCollRequested()` must taken into account the exit fees of the exposure token. This has a closed formula by using these 3 invariants:

1. Computing final totalAssets() to maintain the same ratio in the vault.
2. Debt_final = Collateral_final * ICR
3. Exposure_delta = Debt_delta / (1 - lspExitFees) Leading to: [image](<https://github.com/user-attachments/assets/5a17b1d9-3da3-4397-80aa-2517df5ef964>)
