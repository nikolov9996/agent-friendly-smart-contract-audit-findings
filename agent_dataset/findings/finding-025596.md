---
id: 25596
severity: "Crit/High"
---

# DarkPoolAssetManager can be drained by looping over join(), joinSplit() or swap() with only some initial amount

## Description

[DarkPoolAssetManager::join()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/DarkpoolAssetManager.sol#L397>), [DarkPoolAssetManager::joinSplit()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/DarkpoolAssetManager.sol#L348>) and [DarkPoolAssetManager::swap()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/DarkpoolAssetManager.sol#L441>) don't check if the 2 notes are the same.

Thus, using only 1 note, it's possible to double the amount of funds available. When used in a loop, this enables draining the whole asset manager.

[Here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/commit/59dbe1b6625d180ec7a7c367169fd6386d1a077c>) is the poc for join() and joinSplit and [here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/fuzzing/test/foundry/DarkpoolAssetManager.t.sol#L460>) for swap().

## Proof of Concept

No PoC provided.

## Recommendation

Check if the input notes are the same.
