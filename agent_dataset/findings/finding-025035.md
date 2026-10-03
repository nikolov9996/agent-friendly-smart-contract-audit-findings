---
id: 25035
severity: "Medium"
---

# ManagedLeveragedVault::decreaseLeverage() will not work when it goes below the minimum debt

## Description



## Proof of Concept

## Vulnerability Detail

There is no consideration for the minimum debt in this function:

```solidity
function decreaseLeverage(
    uint256 _exposureAmount,
    address _upperHint,
    address _lowerHint,
    ExternalRebalanceParams memory params
) external onlyOwnerOrKeeper nonReentrant returns (uint256 debt) {
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();
    ManagedLeveragedVaultStorage storage $ = _getManagedLeveragedVaultStorage();

    debt = _rebalance(
        RebalanceParams({
            sentCurrency: $.exposureToken,
            sentAmount: _exposureAmount,
            receivedCurrency: address(b$.nect),
            ext: params
        })
    );

    b$.borrowerOperations.repayDebt(
        b$.denManager,
        address(this),
        debt,
        _upperHint,
        _lowerHint
    );

    _checkInvariantICR(getCurrentDenICR(), getTargetICR(), Tolerance.ABOVE);
}
```

And the last check forces the ICR to reach the target. Hence, it may not be possible to deleverage at all risking liquidation. It should be possible to deleverage the maximum possible until the minimum debt is reached.

## Impact

Liquidation/redemption risk.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR472](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR472>)

## Recommendation

The target ICR requirement could be soften.
