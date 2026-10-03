---
id: 25603
severity: "Medium"
---

# Some ETH transfers don't revert if they fail

## Description

ETH transfers should revert if they fail. Although this issue alone will not lead to exploits, it increases the attack surface.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if the transfers fails in:

- [Curve remove liquidity](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveRemoveLiquidityAssetManager.sol#L453>).
- [Curve multi exchange](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveMultiExchangeAssetManager.sol#L208-L216>).
- [Curve single exchange](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/fuzzing/contracts/defi/curve/CurveSingleExchangeAssetManager.sol#L180-L188>).
