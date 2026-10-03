---
id: 25090
severity: "Crit/High"
---

# Yield loss due to StrategyRouterLib:rebalanceStrategies() not allocating saturated strategy deposits

## Description

StrategyRouterLib:rebalanceStrategies() withdraws excess funds from strategies and adds it up to the router balance. When strategies have less funds than desired, it first stores in [strategyDatas[i].toDeposit](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L574>) the amount to be deposited.

As can be seen in the previous code link, the strategy was not completely saturated, so the weight is bigger than 0, the funds were sent to the strategy, but deposit() was not called yet.

Then, if the remaining weight of the strategy is [less than ALLOCATION_THRESHOLD](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L603>), it skips the current strategy, never depositing the previous saturated weight.

If it is bigger than ALLOCATION_THRESHOLD, it still skips the deposit of the previously saturated weight, due to the fact that it overrides strategyDatas[i].toDeposit [(L639](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L639>), [L662](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L662>) and [L684](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L684>)).

Thus, when it calls [`strategy.deposit()`](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L698>), it only sends the value of the last swap, without taking into account the previously accumulated strategyDatas[i].toDeposit values.

## Proof of Concept

No PoC provided.

## Recommendation

Change strategyDatas[i].toDeposit = received; to strategyDatas[i].toDeposit += received; in L639, L662 and L684. Also, when the remaining weight of the strategy equals less than `ALLOCATION_THRESHOLD`, deposit strategyDatas[i].toDeposit before continuing.
