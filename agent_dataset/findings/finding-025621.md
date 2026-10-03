---
id: 25621
severity: "Crit/High"
---

# Stuck ETH in Curve exchanges due to sending msg.value to the exchange instead of amountIn

## Description

The curve exchanges allow users who deposited to use their note commitments to swap for other assets. Thus, they have already deposited the ETH, but the exchanges still [require](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/defi/curve/CurveSingleExchangeAssetManager.sol#L146>) the amountIn to be msg.value, leading to stuck ETH.

POC [here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/fuzzing/test/foundry/CurveSingleExchangeAssetManager.t.sol#L68>).

## Proof of Concept

No PoC provided.

## Recommendation

Replace IExchange(exchangeContract).exchange{value: msg.value} by IExchange(exchangeContract).exchange{value: amountIn}.
