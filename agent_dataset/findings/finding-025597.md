---
id: 25597
severity: "Crit/High"
---

# DarkpoolAssetManager::Split() into 2 equal amounts leads to lost funds

## Description

When using [DarkpoolAssetManager::Split()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/DarkpoolAssetManager.sol#L303>), [there](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/commit/caed73d878d323b218fbef82094264528478c61f>) is no check to make sure that the 2 resulting notes are not equal, making it impossible to use the second note after the first one as the nullifier will be used by then.

Check the poc here.

## Proof of Concept

No PoC provided.

## Recommendation

In DarkpoolAssetManager::Split() add a _noteOut1 != _noteOut2 check.
