---
id: 25096
severity: "Low/Info"
---

# Lost NFT if farmingContract is incorrectly set

## Description

In [PHyperLPoolSwapInside::_depositNftToFarm()](<https://github.com/ClipFinance/StrategyRouter-private/blob/v3-vault-swap-inside/contracts/liquidityManagment/PHyperLPoolSwapInside.sol#L454-L456>), the NFT transfer will succeed if the farmingContract is incorrectly set.

This is a possibility as the contracts are intended to be deployed in more than 1 chain, with [different](<https://docs.pancakeswap.finance/developers/smart-contracts/pancakeswap-exchange/v3-contracts>) addresses.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
