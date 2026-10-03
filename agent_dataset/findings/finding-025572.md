---
id: 25572
severity: "Medium"
---

# Price formula in TpdaLiquidationPair._computePrice() does not account for a jump in liquidatable balance

## Description



## Proof of Concept

## Vulnerability Detail

The price paid by liquidation bots to liquidate the asset balance in a vault is calculated in `TpdaLiquidationPair._computePrice()` as shown:

[TpdaLiquidationPair.sol#L191-L195](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-tpda-liquidator/src/TpdaLiquidationPair.sol#L191-L195>)

```solidity
        uint256 elapsedTime = block.timestamp - lastAuctionAt;
        if (elapsedTime == 0) {
            return type(uint192).max;
        }
        uint192 price = uint192((targetAuctionPeriod * lastAuctionPrice) / elapsedTime);
```

As seen from above, the price paid decreases linearly over time from `targetAuctionPeriod * lastAuctionPrice` to 0. This allows the liquidation pair to naturally find a price that liquidation bots are willing to pay for the current liquidatable balance in the vault, which is calculated as shown:

[TpdaLiquidationPair.sol#L184-L186](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-tpda-liquidator/src/TpdaLiquidationPair.sol#L184-L186>)

```solidity
    function _availableBalance() internal returns (uint256) {
        return ((1e18 - smoothingFactor) * source.liquidatableBalanceOf(address(_tokenOut))) / 1e18;
    }
```

The vault's liquidatable balance is determined by `liquidatableBalanceOf()`:

[PrizeVault.sol#L687-L709](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-vault/src/PrizeVault.sol#L687-L709>)

```solidity
    function liquidatableBalanceOf(address _tokenOut) external view returns (uint256) {
        uint256 _totalDebt = totalDebt();
        uint256 _maxAmountOut;
        if (_tokenOut == address(this)) {
            // Liquidation of vault shares is capped to the mint limit.
            _maxAmountOut = _mintLimit(_totalDebt);
        } else if (_tokenOut == address(_asset)) {
            // Liquidation of yield assets is capped at the max yield vault withdraw plus any latent balance.
            _maxAmountOut = _maxYieldVaultWithdraw() + _asset.balanceOf(address(this));
        } else {
            return 0;
        }

        // The liquid yield is limited by the max that can be minted or withdrawn, depending on
        // `_tokenOut`.
        uint256 _availableYield = _availableYieldBalance(totalPreciseAssets(), _totalDebt);
        uint256 _liquidYield = _availableYield >= _maxAmountOut ? _maxAmountOut : _availableYield;

        // The final balance is computed by taking the liquid yield and multiplying it by
        // (1 - yieldFeePercentage), rounding down, to ensure that enough yield is left for
        // the yield fee.
        return _liquidYield.mulDiv(FEE_PRECISION - yieldFeePercentage, FEE_PRECISION);
    }
```

Apart from the yield vault suddenly gaining yield, there are two reasons why the vault's liquidatable balance might suddenly increase:

- (1) The liquidatable balance is no longer restricted by the mint limit after someone withdraws from the vault. For example:
- Assume `_tokenOut == address(this)`.
- The vault is currently at the mint limit, so `_maxAmountOut = _mintLimit(_totalDebt) = 0`.
- A user withdraws from the vault, causing the mint limit to decrease. Assume that `_maxAmountOut` is now `1000e18`, which means 1000 more shares can be minted.
- Since `_liquidYield` is restricted by `_maxAmountOut`, it jumps from `0` to `1000e18`, causing a sudden increase in the liquidatable balance.
- (2) The vault's owner calls `setYieldFeePercentage()` to decrease `yieldFeePercentage`. As seen from above, this will cause the returned value from `liquidatableBalanceOf()` to suddenly increase.

However, since the vault's liquidatable balance is not included in price calculation and the price decreases linearly, `TpdaLiquidationPair._computePrice()` cannot accurately account for instantaneous increases in `liquidatableBalanceOf()`.

Using (1) to illustrate this:

- Assume that the vault's token is USDT and the prize token is USDC.
- Since the vault is currently at its mint limit, the liquidatable balance is 0 USDT.
- Over time, the price calculated in `_computePrice()` decreases to near-zero to match the liquidatable balance.
- A user suddenly withdraws, which increases the mint limit and causes the liquidatable balance to jump to 1000 USDT.
- However, the price returned by `_computePrice()` will still remain close to 0 USDC.
- This allows a liquidation bot to swap 1000 USDT in the vault for 0 USDC.

As seen from above, when a sudden increase in liquidatable balance occurs, the price in `_computePrice()` could be too low due to the linearly decreasing auction.

## Impact

When `liquidatableBalanceOf()` suddenly increases due to an increase in the mint limit or a reduction in `yieldFeePercentage`, liquidation bots can swap the liquidatable balance in the vault for less than its actual value. This causes a loss of funds for the vault, and by extension, all users in the vault.

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-tpda-liquidator/src/TpdaLiquidationPair.sol#L191-L195](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-tpda-liquidator/src/TpdaLiquidationPair.sol#L191-L195>)

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-tpda-liquidator/src/TpdaLiquidationPair.sol#L184-L186](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-tpda-liquidator/src/TpdaLiquidationPair.sol#L184-L186>)

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-vault/src/PrizeVault.sol#L687-L709](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-vault/src/PrizeVault.sol#L687-L709>)

## Recommendation

Consider using an alternative auction formula in `_computePrice()`, ideally one that takes into account the current liquidatable balance in the vault.
