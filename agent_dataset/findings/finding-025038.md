---
id: 25038
severity: "Low/Info"
---

# Hints on withdrawal may fail as the ICR changes between claiming collateral surplus and repaying debt

## Description



## Proof of Concept

## Vulnerability Detail

The `ManagedLeveragedVault::executeWithdrawalEpoch()` is as follows:

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
        _maxFeePercentage: 0,
        _collDeposit: 0,
        _collWithdrawal: cd.collVaultSharesToWithdraw,
        _debtChange: cd.debtToUnwind,
        _isDebtIncrease: false,
        _upperHint: params.upperHint,
        _lowerHint: params.lowerHint
    });
```

It uses the same hints for 2 different intances, with different ICRs each time. Hence, there is a chance the transaction reverts.

## Impact

DoSed `ManagedLeveragedVault::executeWithdrawalEpoch()`. Workaround is possible by manually claiming collateral surplus before calling it.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/blob/main/blockend/src/core/boyco/ManagedLeveragedVault.sol#L297-L314](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/blob/main/blockend/src/core/boyco/ManagedLeveragedVault.sol#L297-L314>)

## Recommendation

Send different hints.
