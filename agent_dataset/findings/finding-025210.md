---
id: 25210
severity: "Crit/High"
---

# UniswapV2Swapper uses block.timestamp for deadline [Out of scope]

## Description

Uniswap sets a deadline to limit arbitrage opportunities if the swap does not get included right away. If the swap specifies a deadline of block.timestamp, then the swap transaction can be included in any block.

This means that the price can, by then, have changed significantly.

## Proof of Concept

No PoC provided.

## Recommendation

Send a deadline argument.
