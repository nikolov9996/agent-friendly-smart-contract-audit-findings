---
id: 25109
severity: "Crit/High"
---

# tower.gameETHForWithdraw should be reduced pro-rata when there is not enough ETH

## Description

`Codeup::withdraw()` and `Codeup::reinvest()` cap the withdrawn amount to the available `ETH` balance, but always set the `tower.gameETHForWithdraw` to `0`, which means that a user can have a significant amont of `gameETH` for withdraw, but due to the contract having low `ETH` balance, most of these funds could be lost.

This is relevant because blockchains often have concurrency issues, which means, for example, 2 users trying to withdraw more than the contract balance at the same time could lead to one of them getting much less `ETH` than expected.

## Proof of Concept

No PoC provided.

## Recommendation

When there is not enough `ETH`,`tower.gameETHForWithdraw` should be reduced by the `amount` before subtracting the commission divided by the price, rounded up.
