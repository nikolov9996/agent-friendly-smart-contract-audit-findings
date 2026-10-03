---
id: 25686
severity: "Low/Info"
---

# MidnightSupplyVaultSharesCallback deposits into ERC4626 without a min shares slippage bound

## Description



## Proof of Concept

## Vulnerability Detail

The callback's [deposit](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/callbacks/MidnightSupplyVaultSharesCallback.sol#L65>) accepts whatever shares the vault returns:

```solidity
IERC20(loanToken).forceApprove(vault, totalDeposit);
uint256 shares = IERC4626(vault).deposit(totalDeposit, address(this));

IERC20(vault).forceApprove(address(MORPHO_MIDNIGHT), shares);
MORPHO_MIDNIGHT.supplyCollateral(market, callbackData.collateralIndex, shares, seller);
```

The borrower configures `CallbackData` when creating the sell offer. The offer sits open until a taker fills it, which may happen much later. When `additionalDepositPercent > 0`, fresh borrower funds are also pulled in via `safeTransferFrom`, so the borrower's own capital flows into the vault at the share price observed at fill time.

If the vault's share price degrades between offer creation and offer fill (vault loss, oracle drift, hostile curator action), the borrower receives fewer shares than expected, supplying less collateral than intended and ending up with a smaller LTV buffer than they signed up for.

The user-facing `MidnightVaultExecutor` enforces `maxSharePriceE27` for the exact same flow ([reference](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/MidnightVaultExecutor.sol#L70-L73>)), but the offer-fill callback omits it.

## Impact

The borrower's collateral position is exposed to ERC4626 share price drift with no cap, weakening their health factor relative to what the offer parameters implied.

## Code Snippet

[https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/callbacks/MidnightSupplyVaultSharesCallback.sol#L65](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/callbacks/MidnightSupplyVaultSharesCallback.sol#L65>)

## Recommendation

Add a `maxSharePriceE27` (or `minShares`) field to `CallbackData` and revert when the realized share price exceeds it, matching the `MidnightVaultExecutor` pattern. Or document that the vault is safe.
