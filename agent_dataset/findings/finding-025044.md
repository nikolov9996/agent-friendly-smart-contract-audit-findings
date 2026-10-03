---
id: 25044
severity: "Medium"
---

# Protocol will need to donate minimum debt for all new ManagedLeveragedVaults

## Description



## Proof of Concept

## Vulnerability Detail

See `ManagedLeveragedVault::deposit()`:

```
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

It tries to add collateral, but it reverts before the Den is opened. As opening a Den requires minimum debt (and thus minimum collateral), the only way to have assets when opening is by donating.

## Impact

Protocol needs to donate min debt, and can't recover these funds.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR507](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR507>)

## Recommendation

Let users deposit before the Den is opened (just let the funds idle instead of adding collateral).
