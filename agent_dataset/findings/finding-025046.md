---
id: 25046
severity: "Medium"
---

# ManagedLeveragedVault.sol::deposit() is missing slippage control

## Description



## Proof of Concept

## Vulnerability Detail

The deposit function is as follows:

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

Note that there is no slippage control on the shares amount minted, whose ratio may change depending on several protocol actions or price updates. There is slippage control for the `collVaultShares`, but this may still mean a lower amount of shares as they are not 100% related.

## Impact

User takes slippage losses.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR273](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR273>)

## Recommendation

Add slippage control to shares.
