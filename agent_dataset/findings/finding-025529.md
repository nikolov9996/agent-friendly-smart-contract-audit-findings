---
id: 25529
severity: "Medium"
---

# Inability to Close Positions with Significant Positive PnL

## Description

Presently, when there isn't adequate liquidity in the OstiumVault to cover profits for trades with substantial positive PnL, a revert occurs. While this behavior is intended, it's worth considering implementing a solution to partially receive the profit up to a maximum threshold or at least the collateral itself.

Otherwise, traders won't be able to exit a position at all.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
