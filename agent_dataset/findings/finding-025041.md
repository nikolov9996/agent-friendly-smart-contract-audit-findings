---
id: 25041
severity: "Crit/High"
---

# Lost withdrawals due to ManagedLeveragedVault::openDen() using all asset() balance

## Description



## Proof of Concept

## Vulnerability Detail

`ManagedLeveragedVault::executeWithdrawalEpoch()` converts collateral vault shares to assets and leaves them in the contract.

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

    /// @dev Have assets sitting on the contract for `withdrawFromEpoch` to claim
    uint256 assets = _rebalance(
            RebalanceParams({
                sentCurrency: address(b$.collVault),
                sentAmount: cd.collVaultSharesToWithdraw,
                receivedCurrency: asset(),
                ext: params.unwrapParams
            })
        );
    ...
}
```

`ManagedLeveragedVault::openDen()` picks up all `asset()` available, including the ones reserved for withdrawal.

```solidity
function openDen(
    uint256 _maxFeePercentage,
    uint256 _minCollVaultShares,
    address _upperHint,
    address _lowerHint
) external onlyOwner {
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();

    IDenManager denManager = IDenManager(b$.denManager);

    uint256 status = denManager.getDenStatus(address(this));
    if (DenStatus(status) != DenStatus.active) revert AlreadyOpened();

    uint256 collVaultShares;
    uint256 assetsAmount = IERC20(asset()).balanceOf(address(this));
    if (assetsAmount != 0) {
        IERC20(asset()).approve(address(b$.collVault), assetsAmount);
        collVaultShares = b$.collVault.deposit(assetsAmount, address(this));
        if (collVaultShares < _minCollVaultShares) revert VaultSlippage(_minCollVaultShares, collVaultShares);
    }
    ...
}
```

## Impact

DoSed withdrawals, loss of funds as the shares/assets ratio will be off because the shares were already burned.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR521](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR521>)

## Recommendation

Include the reserved assets for withdrawal in the calculation.
