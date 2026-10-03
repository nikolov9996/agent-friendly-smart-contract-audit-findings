---
id: 25623
severity: "Low/Info"
---

# Uniswap collect fees should skip collecting fees of one of the tokens if the amount is 0

## Description

Uniswap positions may collect fees in only of the tokens, leading to 0 fees in the other. This will cause the fee manager to revert in [calculateFee()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/FeeManager.sol#L105-L108>).

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
