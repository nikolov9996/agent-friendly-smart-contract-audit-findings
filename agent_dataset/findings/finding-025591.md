---
id: 25591
severity: "Medium"
---

# CurveAddLiquidityAssetManager::curveAddLiquidity() does not deal correctly with isLegacy = 0b10 and ETH

## Description

If isETH, but args.isLegacy is 1, it wraps to weth and allows pool, see [here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveAddLiquidityAssetManager.sol#L229>). if args.islegacy is 0b10 and the asset is ETH, it does not send ETH to the pool, [here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveAddLiquidityAssetManager.sol#L262-L279>).

Additionally, it seems that it expects the ether balance to [increase](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L696-L699>), which is unexpected, [mintAmount](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapLiquidityAssetManager.sol#L748-L750>) = address(this).balance - initAmount;, as can be seen [here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveAddLiquidityAssetManager.sol#L276>).

## Proof of Concept

No PoC provided.

## Recommendation

It seems that the mintAmount would always be IERC20(_args.lpToken).balanceOf(address(this)) - initAmount, where initAmount = IERC20(_args.lpToken).balanceOf(address(this));, but a pool example should be given to confirm.
