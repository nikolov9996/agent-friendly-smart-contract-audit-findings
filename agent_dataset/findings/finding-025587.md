---
id: 25587
severity: "Crit/High"
---

# _addLiquidity() slippage is incorrectly set

## Description

The slippage is computed as:

```solidity
mintAmount = _args.isLegacy & 12 == 12 ? IPools(_args.pool).calc_token_amount(curveInputAmounts) : IPools(_args.pool).calc_token_amount(curveInputAmounts, true);
mintAmount = (mintAmount / 100) * 95;
```

This gets the mintAmount value post price manipulation, rendering the slippage protection useless. Also, hardcoding a parameter of 95% slippage is not ideal. [Here](<https://solodit.xyz/issues/m-05-wrong-slippage-check-code4rena-redacted-cartel-redacted-cartel-contest-git>) is a similar finding.

## Proof of Concept

No PoC provided.

## Recommendation

There are 2 solutions to this problem:

1. Send the minimum mint amount as an argument.
2. Use an offchain oracle such as Chainlink.
