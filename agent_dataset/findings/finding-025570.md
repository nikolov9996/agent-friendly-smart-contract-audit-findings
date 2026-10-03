---
id: 25570
severity: "Medium"
---

# DoSed liquidations as PrizeVault::liquidatableBalanceOf() does not take into account the mintLimit when the token out is the asset

## Description



## Proof of Concept

## Vulnerability Detail

`TpdaLiquidationPair::_availableBalance()` is called in `TpdaLiquidationPair::swapExactAmountOut()` to revert if the amount to liquidate exceeds the maximum and in `TpdaLiquidationPair::maxAmountOut()` to get the maximum liquidatable amount. Thus, users or smart contracts will [call](<https://dev.pooltogether.com/protocol/guides/bots/liquidating-yield/#2-compute-the-available-liquidity>) `TpdaLiquidationPair::maxAmountOut()` to get the maximum amount out and then `TpdaLiquidationPair::swapExactAmountOut()` with this amount to liquidate.

> Compute how much yield is available using the [maxAmountOut](<https://dev.pooltogether.com/protocol/reference/liquidator/TpdaLiquidationPair#maxamountout>) function on the Liquidation Pair. This function returns the maximum number of tokens you can swap out.

However, this is going to revert whenever the minted yield fee exceeds the mint limit, as `PrizeVault::liquidatableBalanceOf()` does not consider it when the asset to liquidate is the asset of the `PrizeVault`. Consider `PrizeVault::liquidatableBalanceOf()`:

```solidity
function liquidatableBalanceOf(address _tokenOut) external view returns (uint256) {
    ...
    } else if (_tokenOut == address(_asset)) { //@audit missing yield percentage for mintLimit
        // Liquidation of yield assets is capped at the max yield vault withdraw plus any latent balance.
        _maxAmountOut = _maxYieldVaultWithdraw() + _asset.balanceOf(address(this));
    }
    ...
}
```

As can be seen from the code snipped above, the minted yield fee is not taken into account and the mint limit is not calculated. On `PrizeVault::transferTokensOut()`, a mint fee given by `_yieldFee = (_amountOut * FEE_PRECISION) / (FEE_PRECISION - _yieldFeePercentage) - _amountOut;` is always minted and the limit is enforced at the end of the function `_enforceMintLimit(_totalDebtBefore, _yieldFee);`. Thus, without limiting the liquidatable assets to the amount that would trigger a yield fee that reaches the mint limit, liquidations will be DoSed.

## Impact

DoSed liquidations when the asset out is the asset of the `PrizeVault`.

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-vault/src/PrizeVault.sol#L693-L696](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-vault/src/PrizeVault.sol#L693-L696>)

## Recommendation

The correct formula can be obtained by inverting `_yieldFee = (_amountOut * FEE_PRECISION) / (FEE_PRECISION - _yieldFeePercentage) - _amountOut;`, leading to:

```solidity
function liquidatableBalanceOf(address _tokenOut) external view returns (uint256) {
    ...
    } else if (_tokenOut == address(_asset)) {
        // Liquidation of yield assets is capped at the max yield vault withdraw plus any latent balance.
        _maxAmountOut = _maxYieldVaultWithdraw() + _asset.balanceOf(address(this));
        // Limit to the fee amount
        uint256  mintLimitDueToFee = (FEE_PRECISION - yieldFeePercentage) * _mintLimit(_totalDebt) / yieldFeePercentage;
       _maxAmountOut = _maxAmountOut >= mintLimitDueToFee ? mintLimitDueToFee : _maxAmountOut;
    }
    ...
}
```
