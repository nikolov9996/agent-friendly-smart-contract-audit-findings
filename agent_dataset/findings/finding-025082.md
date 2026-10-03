---
id: 25082
severity: "Medium"
---

# Potential overflow in PancakeSwapPlugin:getRoutePrice()

## Description

Currently the price is [calculated](<https://github.com/ClipFinance/StrategyRouter-private/blob/Audit-fixes/contracts/exchange/PancakeSwapPlugin.sol#L284>) as uint256 routePrice = FullMath.mulDiv(uint256(sqrtPriceX96) * uint256(sqrtPriceX96), precision0, 2 ** (96 * 2));.

Doing uint256(sqrtPriceX96) * uint256(sqrtPriceX96) might overflow as 2 uint160 variables may result in a number with more than 256 bits. The correct way of calculating this is in OracleLibrary:getQuoteAtTick(), [here](<https://github.com/pancakeswap/pancake-v3-contracts/blob/main/projects/v3-periphery/contracts/libraries/OracleLibrary.sol#L49>).

Note: also [here](<https://github.com/ClipFinance/StrategyRouter-private/blob/Audit-fixes/contracts/liquidityManagment/PHyperLPool.sol#L281>).

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
