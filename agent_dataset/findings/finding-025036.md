---
id: 25036
severity: "Low/Info"
---

# ManagedLeveragedVault::deposit() slippage control on collVaultShares is not intuitive

## Description



## Proof of Concept

## Vulnerability Detail

The deposit function is:

```solidity
function deposit(uint256 assets, address receiver, AddCollParams calldata params)
    public
    notPaused
    nonReentrant
    returns (uint256 shares)
{
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();

    shares = _deposit(assets, receiver);

    IERC20(asset()).forceApprove(address(b$.collVault), assets);
    uint256 collVaultShares = b$.collVault.deposit(assets, address(this));

    if (collVaultShares < params.minSharesOut) revert VaultSlippage(params.minSharesOut, collVaultShares);

    _addColl(collVaultShares, params.upperHint, params.lowerHint);
}
```

The user deposits assets and pays entry fees. However, the `params.minSharesOut` parameter is compared against `collVaultShares`, which comes from converting the whole assets deposited into collateral vault shares. This can be unexpected for users as slippage control on a deposit function should be on the amount the user actually gets (assets minus entry fees), but it currently compares against all assets deposited.

## Impact

UX issues. Some users may be caught off guard but it only leads to reverts at max.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR278](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR278>)

## Recommendation

Apply slippage control to the net `collVaultShares` the user mints.
