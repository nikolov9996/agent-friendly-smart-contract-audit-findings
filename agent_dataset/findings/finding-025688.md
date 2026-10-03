---
id: 25688
severity: "Low/Info"
---

# MidnightVaultExecutor::onLiquidate forces liquidators to provide callback data and never refunds leftover loan tokens

## Description



## Proof of Concept

## Vulnerability Detail

In [onLiquidate](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/MidnightVaultExecutor.sol#L222>), the redeemed underlying is unconditionally sent to the liquidator:

```solidity
uint256 redeemed = IERC4626(vault).redeem(seizedShares, liquidator, address(this));

if (minSharePriceE27 != 0 && UtilsLib.mulDivDown(redeemed, RAY, seizedShares) < minSharePriceE27) {
    revert SlippageExceeded();
}

if (callbackData.length > 0) {
    require(
        ILiquidateCallback(liquidator).onLiquidate(...) == CALLBACK_SUCCESS,
        IMidnight.WrongLiquidateCallbackReturnValue()
    );
}
```

After `onLiquidate` returns, Midnight pulls `repaidUnits` of loan token from the executor. With `callbackData.length == 0`, no one has transferred the loan token back to the executor, so the pull reverts and the liquidation fails. The only liquidators that work are ones that implement `ILiquidateCallback`.

Compare with [onRepay](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/MidnightVaultExecutor.sol#L132-L164>), which routes the redeem recipient based on whether callback data is present:

```solidity
address recipient = callbackData.length > 0 ? caller : address(this);
uint256 redeemed = IERC4626(vault).redeem(sharesToWithdraw, recipient, address(this));
```

Additionally, [repayAndWithdrawCollateral](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/MidnightVaultExecutor.sol#L123-L126>) sweeps leftover loan tokens back to the caller, but `liquidateAndRedeem` and `onLiquidate` do not. Any loan-token dust left on the executor after the liquidation is forfeited and may be swept by the next caller.

## Impact

EOA liquidators and any liquidator without a Midnight-compatible callback contract are DoSed from liquidating vault-share collateral through the executor. Any leftover loan tokens on the executor after a successful liquidation are forfeited.

## Code Snippet

[https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/MidnightVaultExecutor.sol#L222](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/MidnightVaultExecutor.sol#L222>)

## Recommendation

Mirror the `onRepay` pattern: redeem to `address(this)` when there is no callback data, and only forward to the liquidator inside the callback branch. After the liquidation completes in `liquidateAndRedeem`, transfer the redeemed loan token and any dust to the liquidator:

```solidity
address recipient = callbackData.length > 0 ? liquidator : address(this);
uint256 redeemed = IERC4626(vault).redeem(seizedShares, recipient, address(this));
```

And in `liquidateAndRedeem`, sweep the remaining loan-token balance to `msg.sender` after the `MORPHO_MIDNIGHT.liquidate` call returns.
