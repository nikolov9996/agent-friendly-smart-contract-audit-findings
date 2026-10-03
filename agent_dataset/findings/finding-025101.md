---
id: 25101
severity: "Low/Info"
---

# Unnecessary abi.decode in PHyperLPoolSwapInside::_swapWithCustomData()

## Description

[PHyperLPoolSwapInside::_swapWithCustomData()](<https://github.com/ClipFinance/StrategyRouter-private/blob/v3-vault-swap-inside/contracts/liquidityManagment/PHyperLPoolSwapInside.sol#L592>) does abi.decode of the returnData, which is already a bytes variable.

## Proof of Concept

No PoC provided.

## Recommendation

revert(string(returnData)); should be enough
