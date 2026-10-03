---
id: 25085
severity: "Medium"
---

# DoSed StrategyRouter:withdrawFromStrategies() if strategyTokenBalancesUsd[i] is too small in the swapping phase

## Description

StrategyRouter:withdrawFromStrategies() withdraws from the idle strategy of the withdraw token and then tries to withdraw from idle strategies and later strategies with other tokens.

It tries to swap from idle strategies and strategies if there is still not enough usd, skipping the swap if [idleStrategyTokenBalancesUsd](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouter.sol#L755-L757>) or [strategyTokenBalancesUsd](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouter.sol#L796-L798>) are 0.

However, when the balance is very small, it will likely be swapped into a 0 amount due to slippage, making it [revert](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/exchange/Exchange.sol#L138>). This can be exploited by griefers by sending 1 amount to an idle strategy so it reverts.

## Proof of Concept

No PoC provided.

## Recommendation

Define a threshold to swap, similarly to the allocation threshold.
