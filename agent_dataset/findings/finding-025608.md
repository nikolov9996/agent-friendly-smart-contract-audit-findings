---
id: 25608
severity: "Crit/High"
---

# Attackers can include other users nullifiers to make their funds stuck when adding liquidity to curve

## Description

[CurveLiquidityAssetManager::curveAddLiquidity()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveAddLiquidityAssetManager.sol#L112>) always spends the nullifiers, even if the amounts used are 0.

In the [circuit](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/circuits/curve_add_liquidity/src/main.nr#L40>), if the amount is 0, it does not validate the nullifier against the user signature, making it possible to include nullifiers from other users in the same transaction and losing their funds forever.

[Here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/fuzzing/test/foundry/CurveLiquidityAssetManager.t.sol#L221>) is the poc.

## Proof of Concept

No PoC provided.

## Recommendation

In CurveAddLiquidityAssetManager::_addLiquidity() skip [_postWithdraw()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveAddLiquidityAssetManager.sol#L435-L437>) if the amount is 0.
