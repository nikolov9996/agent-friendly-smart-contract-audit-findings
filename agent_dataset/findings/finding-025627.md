---
id: 25627
severity: "Low/Info"
---

# UniswapLiquidityAssetManager registers the note footer twice

## Description

The note footers are registered twice. [https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L574-L575](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L574-L575>) [https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L532-L533](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L532-L533>)

## Proof of Concept

No PoC provided.

## Recommendation

Only register once.
