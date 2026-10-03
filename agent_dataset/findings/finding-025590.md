---
id: 25590
severity: "Crit/High"
---

# CurveAssetManagerHelper::_validateAssets() should check that the number of assets provided is smaller than the maximum of the pool

## Description

[CurveAssetManagerHelper::_validateAssets()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveAssetManagerHelper.sol#L212>) allows sending assets with indexes bigger than the maximum allowed of a pool (num_coins). This could lead to users losing tokens or unexpected behaviours.

## Proof of Concept

No PoC provided.

## Recommendation

Validate that the number of assets sent is at most num_coins.
