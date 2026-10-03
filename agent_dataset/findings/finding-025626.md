---
id: 25626
severity: "Medium"
---

# Uniswap asset managers are missing slippage checks

## Description

All Uniswap [interactions](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L696-L699>) are [missing](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L748-L750>) a deadline argument and are not setting the following slippage protection arguments in UniswapLiquidityAssetManager:

- amount0Min and amount1Min in MintParams.
- amount0Min and amount1Min in DecreaseLiquidityParams. UniswapSwapAssetManager [sets](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapSwapAssetManager.sol#L239C44-L239C56>) the minAmountOut value, but is not signed by the user in the circuit, so it could be gamed.

## Proof of Concept

No PoC provided.

## Recommendation

These arguments should be part of the proof and the user should sign them to prevent slippage.
