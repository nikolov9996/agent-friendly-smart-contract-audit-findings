---
id: 25051
severity: "Medium"
---

# DoSed withdrawals due to ManagedLeveragedVault::executeWithdrawalEpoch() repaying debt above limit

## Description



## Proof of Concept

## Vulnerability Detail

`ManagedLeveragedVault::executeWithdrawalEpoch()` is as follows:

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

If the chain of calls is followed, there is no limit to the `cd.debtToUnwind` calculated, and it may revert when everyone or many users try to withdraw in the same epoch (or last epochs), as the remaining debt would be lower than the min debt of the Den and it would revert. In this case, it would be appropriate to close the Den and allow everyone to withdraw.

## Impact

DoSed withdrawals.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR360](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR360>)

## Recommendation

Close the Den if the remaining debt is below the minimum limit.
