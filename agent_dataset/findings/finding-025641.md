---
id: 25641
severity: "Low/Info"
---

# ERC4626YieldBackend.withdrawSurplus() uses convertToAssets() which doesn't account for fees

## Description



## Proof of Concept

## Vulnerability Detail

The `withdrawSurplus()` function calculates the vault's asset value using `convertToAssets()`:

```solidity
uint256 vaultAssets = VAULT.convertToAssets(
    VAULT.balanceOf(address(this))
);
```

Per EIP-4626, `convertToAssets()` returns the amount of assets that would be exchanged for the given shares, but it does not account for withdrawal fees. For vaults that charge withdrawal fees, the actual redeemable amount is less than what `convertToAssets()` reports.

This causes the calculated `surplusAmount` to be higher than the actual withdrawable surplus. When `VAULT.withdraw(surplusAmount, ...)` is called, it may:

1. Revert if the vault cannot fulfill the inflated withdrawal amount
2. Withdraw assets that belong to SuperToken holders (not actual surplus)

## Impact

For ERC4626 vaults with withdrawal fees, `withdrawSurplus()` either reverts (DoSing surplus withdrawal) or incorrectly withdraws funds that belong to SuperToken holders, causing a loss for users.

## Code Snippet

[https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L45-L55](<https://github.com/sherlock-audit/2026-01-superfluid-update-jan-13th/blob/main/protocol-monorepo/packages/ethereum-contracts/contracts/superfluid/ERC4626YieldBackend.sol#L45-L55>)

```solidity
function withdrawSurplus(uint256 totalSupply) external {
    (uint256 normalizedTotalSupply, ) = ISuperToken(address(this))
        .toUnderlyingAmount(totalSupply);

    uint256 vaultAssets = VAULT.convertToAssets(
        VAULT.balanceOf(address(this))
    );

    uint256 surplusAmount = vaultAssets + ASSET_TOKEN.balanceOf(address(this)) - normalizedTotalSupply;
    VAULT.withdraw(surplusAmount, SURPLUS_RECEIVER, address(this));
}
```

## Recommendation

Use `previewRedeem()` instead of `convertToAssets()` to get an accurate estimate that includes fees, or use `maxWithdraw()` to get the maximum withdrawable amount:

```solidity
function withdrawSurplus(uint256 totalSupply) external {
    (uint256 normalizedTotalSupply, ) = ISuperToken(address(this))
        .toUnderlyingAmount(totalSupply);

    // Use maxWithdraw to account for fees and other constraints
    uint256 vaultAssets = VAULT.maxWithdraw(address(this));

    uint256 surplusAmount = vaultAssets + ASSET_TOKEN.balanceOf(address(this)) - normalizedTotalSupply;
    VAULT.withdraw(surplusAmount, SURPLUS_RECEIVER, address(this));
}
```
