---
id: 25625
severity: "Low/Info"
---

# UniswapLiquidityAssetManager::uniswapLiquidityProvision() could return tokenId

## Description

[UniswapLiquidityAssetManager::uniswapLiquidityProvision()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L163>) could return the tokenId for better verbosity.

## Proof of Concept

No PoC provided.

## Recommendation

Return the tokenId.
