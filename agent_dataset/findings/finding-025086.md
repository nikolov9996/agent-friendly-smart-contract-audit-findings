---
id: 25086
severity: "Medium"
---

# Batch:withdraw() can be DoSed by frontrunning it with strategyRouter:allocateToStrategies()

## Description

Anyone who wants to withdraw from a batch via Batch:withdraw() can be frontrunned by an allocateToStrategies() call, which increases the cycle id, making the withdrawal [revert](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L214>).

This not only DoS users, but also places them at a loss if they want to withdraw, as they will likely receive shares worth [less](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L286-L288>) than their deposits at the moment the allocation happens.

## Proof of Concept

No PoC provided.

## Recommendation

Make strategyRouter:allocateToStrategies() permissioned so it becomes impossible for malicious users to perform the attack. Additionally, it's probably better to set some sort of fixed interval for the allocations to happen, so users have time to withdraw if they want to.
