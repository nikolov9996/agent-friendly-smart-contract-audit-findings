---
id: 25611
severity: "Low/Info"
---

# Unused noteCommitment parameter in UniswapRemoveLiquidityInputs struct

## Description

UniswapRemoveLiquidityInputs struct [in](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/uniswap/UniswapInputBuilder.sol#L42>) UniswapInputBuilder has a parameter named positionNoteCommitment which is not required.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the mentioned parameter.
