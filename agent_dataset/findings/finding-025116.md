---
id: 25116
severity: "Medium"
---

# Providing liquidity to the AMM does not check the return value of actually provided tokens leading to locked funds.

## Description



## Proof of Concept

## Vulnerability Detail

The `__addLiquidityToAmmUnchecked` function is used to provide liquidity to the RA:CT AMM pair. In the current implementation, `raTolerance` and `ctTolerance` are calculated based on the reserves of the pair during the current transaction with 1% slippage tolerance. The amounts to be provided are determined by the current price ratio in the pair, which ensures that the amounts are almost always exactly what the AMM expects to maintain the `X * Y = K` constant product formula.

```solidity
function __addLiquidityToAmmUnchecked(
        State storage self,
        uint256 raAmount,
        uint256 ctAmount,
        address raAddress,
        address ctAddress,
        IUniswapV2Router02 ammRouter
    ) internal {
        (uint256 raTolerance, uint256 ctTolerance) =
            MathHelper.calculateWithTolerance(raAmount, ctAmount, MathHelper.UNIV2_STATIC_TOLERANCE);

        ERC20(raAddress).approve(address(ammRouter), raAmount);
        ERC20(ctAddress).approve(address(ammRouter), ctAmount);

        (address token0, address token1, uint256 token0Amount, uint256 token1Amount) =
            MinimalUniswapV2Library.sortTokensUnsafeWithAmount(raAddress, ctAddress, raAmount, ctAmount);
        (,, uint256 token0Tolerance, uint256 token1Tolerance) =
            MinimalUniswapV2Library.sortTokensUnsafeWithAmount(raAddress, ctAddress, raTolerance, ctTolerance);

        (,, uint256 lp) = ammRouter.addLiquidity(
            token0, token1, token0Amount, token1Amount, token0Tolerance, token1Tolerance, address(this), block.timestamp
        );

        self.vault.config.lpBalance += lp;
    }
```

The current implementation does not check the actual amounts used by the AMM when providing liquidity. As a result, small differences (1-2 wei of the corresponding token) between the provided amount and the actual amount used by the AMM may remain locked in the contract. These differences arise from rounding in the RA:CT price ratio calculations and the corresponding amounts that should be provided. Over time, these small discrepancies could accumulate, leading to higher amount of locked tokens in the contract.

PoC:

Adjust the `__addLiquidityToAmmUnchecked()` function to:

```solidity
function __addLiquidityToAmmUnchecked(
        State storage self,
        uint256 raAmount,
        uint256 ctAmount,
        address raAddress,
        address ctAddress,
        IUniswapV2Router02 ammRouter
    ) internal {
        (uint256 raTolerance, uint256 ctTolerance) =
            MathHelper.calculateWithTolerance(raAmount, ctAmount, MathHelper.UNIV2_STATIC_TOLERANCE);

        ERC20(raAddress).approve(address(ammRouter), raAmount);
        ERC20(ctAddress).approve(address(ammRouter), ctAmount);

        (address token0, address token1, uint256 token0Amount, uint256 token1Amount) =
            MinimalUniswapV2Library.sortTokensUnsafeWithAmount(raAddress, ctAddress, raAmount, ctAmount);
        (,, uint256 token0Tolerance, uint256 token1Tolerance) =
            MinimalUniswapV2Library.sortTokensUnsafeWithAmount(raAddress, ctAddress, raTolerance, ctTolerance);

        uint256 lp;
        // add one more block to avoid stack too deep errors
        {
            uint256 actual0;
            uint256 actual1;
            (actual0, actual1, lp) = ammRouter.addLiquidity(
                token0, token1, token0Amount, token1Amount, token0Tolerance, token1Tolerance, address(this), block.timestamp
            );
            if(actual0 != token0Amount || actual1 != token1Amount){
                revert();
            }
        }
        self.vault.config.lpBalance += lp;
    }
```

Running the tests with the following function would result in some tests failing due to this difference in provided and used amounts.

## Impact

The impact of these small amounts of locked funds is not significant on their own, but due to the compound effect over time and the high likelihood of this happening with each liquidity provision, the overall severity of the issue should be considered Medium.

## Code Snippet

`VaultLib.__addLiquidityToAmmUnchecked()`: [https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/VaultLib.sol#L55](<https://github.com/sherlock-audit/2024-08-cork-protocol/blob/db23bf67e45781b00ee6de5f6f23e621af16bd7e/Depeg-swap/contracts/libraries/VaultLib.sol#L55>)

## Recommendation

To handle the small differences between the provided and actual amounts used by the AMM, the return values of the `addLiquidity()` function should be checked, as shown in the adjusted `__addLiquidityToAmmUnchecked()` function. This allows the protocol to detect any discrepancies and take appropriate action.

Depending on the protocol's decision, these leftover funds can either be:

- Returned to users to prevent token loss, ensuring they are not penalized by the rounding differences.
- Accounted for by the protocol and later used for liquidity provision or distributed as rewards, thereby ensuring the funds are not wasted and remain within the protocol's ecosystem.
