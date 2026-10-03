---
id: 25084
severity: "Crit/High"
---

# Swapping with deadline as block.timestamp and 0 minimum amount out is vulnerable to MEV

## Description

Exchange:swap() sets minAmountOut to 0 and in the plugins the deadline is set to block.timestamp. This means that miners may hold the transaction and do whatever MEV strategy they wish, stealing users who incur massive slippage.

## Proof of Concept

No PoC provided.

## Recommendation

Send block.timestamp as argument to the functions that call swap and forward it. Additionally, Exchange:calculateMinAmountOut() should always be used to protect from MEV, even if not for stablecoins.
