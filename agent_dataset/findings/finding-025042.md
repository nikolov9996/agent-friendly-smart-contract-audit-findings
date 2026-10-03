---
id: 25042
severity: "Low/Info"
---

# ManagedLeveragedVault::donateCollateral() is missing a slippage check

## Description



## Proof of Concept

## Vulnerability Detail

The function is:

```solidity
function donateCollateral(uint256 _collateralAmount, address _upperHint, address _lowerHint) external onlyOwner {
    BoycoVaultStorage storage b$ = _getBoycoVaultStorage();

    uint256 assetsNeeded = b$.collVault.previewMint(_collateralAmount);
    IERC20(asset()).transferFrom(msg.sender, address(this), assetsNeeded);

    IERC20(asset()).forceApprove(address(b$.collVault), assetsNeeded);
    b$.collVault.mint(_collateralAmount, address(this));

    IERC20(address(b$.collVault)).forceApprove(address(b$.borrowerOperations), _collateralAmount);
    _addColl(_collateralAmount, _upperHint, _lowerHint);

    // TODO consider invariants
}
```

As can be seen, there is no slippage check in the coll vault, possibly leading to fund loss. It may be mitigated by the approval amount.

## Impact

Collateral vaults are not really manipulatable but still it may be possible for the price to change too much.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR492](<https://github.com/sherlock-audit/2025-04-beraborrow-vault-update/pull/1/files#diff-2d972f52027e0ba1065b2de2b424416244bfef9e2a79d2604e1687867f72c91eR492>)

## Recommendation

Add a slippage check.
