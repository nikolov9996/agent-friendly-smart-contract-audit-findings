---
id: 25080
severity: "Medium"
---

# Inconsistent batch:rebalance() behavior when some strategies reach their limit, leading to yield loss

## Description

Strategies are allocated funds pro-rata to their weights. However, when the target of a strategy is reached, it won't be allocated any more funds.

The funds that were supposed to be allocated to a strategy but its limit was reached, will be allocated to other strategies if they are after it in the array [https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L335.However,](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L335.However>) if the strategies that haven't reached their limit are before the strategy whose limit was reached in the array, the extra funds will be allocated to idle strategies instead [https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L288.This](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L288.This>) is because when a strategy reaches its limit, the weight is set to 0, and the total batch unallocated tokens are not decreased.

This means that if the strategy is first, the other strategies will acquire the extra unallocated tokens. But if the strategy is last, the tokens won't be allocated and will be sent to idle strategies instead.

## Proof of Concept

No PoC provided.

## Recommendation

Cap the weight of a strategy to the amount required for the strategy to reach its limit, before allocating any funds. Note: rebalanceStrategies() ignores the capacity data, which means that it would likely surpass the limit if called afterwards.
