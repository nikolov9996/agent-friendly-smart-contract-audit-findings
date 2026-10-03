---
id: 25106
severity: "Low/Info"
---

# Missing key zero value check

## Description

`gameETHForWithdrawRate` is set in `Codeup::constructor()` to `_gameETHPrice / 1000` but a zero check is missing.

## Proof of Concept

No PoC provided.

## Recommendation

Add the `_checkValue()` function to `gameETHForWithdrawRate = _checkValue(_gameETHPrice / 1000)`.
