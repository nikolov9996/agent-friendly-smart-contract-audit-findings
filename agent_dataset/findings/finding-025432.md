---
id: 25432
severity: "Crit/High"
---

# Funds may be stolen by calling onMoreFlashLoan() directly

## Description

LoopStrategy::onMoreFlashLoan() does not validate that the caller is the market, which allows attackers to steal collateral by calling it directly.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if the caller is not markets.
