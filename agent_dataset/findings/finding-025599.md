---
id: 25599
severity: "Crit/High"
---

# Anyone can deposit to DarkpoolAssetManager as the owner can be freely chosen without any implication

## Description

[DarkpoolAssetManager::depositETH()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/DarkpoolAssetManager.sol#L129-L132>) and [DarkpoolAssetManager::depositERC20()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/DarkpoolAssetManager.sol#L89-L92>) allow choosing any owner, while the msg.sender still receives the deposit.

## Proof of Concept

No PoC provided.

## Recommendation

The owner should be the msg.sender or the owner's signature should be validated (so it can be relayed).
