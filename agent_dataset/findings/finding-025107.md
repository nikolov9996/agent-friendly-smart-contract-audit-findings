---
id: 25107
severity: "Crit/High"
---

# Significant rounding errors due to gameETH not having precision

## Description

In `Codeup::addGameETH()` and `Codeup::reinvest()`, `gameETH` is obtained as `gameETH = amount / gameETHPrice`, which means there may be rounding errors. `gameETH` has no decimals as can be confirmed by the return values of `Codeup::_getUpgradePrice()` and `Codeup::_getYield()`, which have no extra precision.

Thus, as `gameETHPrice` may be a big value - currently `1e12` in the tests, the rounding error may be up to `1e12 - 1`, which is approx `0.0023 USD`. If the price is increased, the rounding error grow to bigger values causing significant loss of funds for users.

## Proof of Concept

No PoC provided.

## Recommendation

Add some precision to `gameETH` by scaling the values in the functions `Codeup::_getUpgradePrice()` and `Codeup::_getYield()` and decreasing the `gameETHPrice` so `gameETH` inherits the decimals of `ETH`.
