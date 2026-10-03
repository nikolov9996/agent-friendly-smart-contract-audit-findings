---
id: 25624
severity: "Crit/High"
---

# UniswapLiquidityAssetManager::_validateCollectFeesArgs() validates nullifier instead of note footer

## Description

UniswapLiquidityAssetManager::_validateCollectFeesArgs() [allows](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L368-L369>) using the same note footers as it checks for nullifiers, when it should check for note footers.

## Proof of Concept

No PoC provided.

## Recommendation

Check for note footers correctly.
