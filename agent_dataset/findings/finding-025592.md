---
id: 25592
severity: "Crit/High"
---

# All curve params should be signed by the schnorr private key in the proof, or users may be griefed

## Description

An example of this issue is for example [here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveRemoveLiquidityAssetManager.sol#L224-L227>).

If the last bit of isLegacy is 0, it checks address(this).balance, otherwise it IERC20(_WETH_ADDRESS).balanceOf(address(this)). This means that if for the same pool, the wrong isLegacy is used, 0 outAmounts[i] will be recorded.

## Proof of Concept

No PoC provided.

## Recommendation

Either send the curve params in the proof and sign them with the schnorr private key or set a mapping from pool to the correct pool params.
