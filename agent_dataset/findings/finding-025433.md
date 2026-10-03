---
id: 25433
severity: "Low/Info"
---

# In case of high ltv and unfavourable swap, onMoreFlashLoan() may underflow

## Description

LoopStrategy::onMoreFlashLoan() underflows when cost > collateralToWithdraw, which may happen in case the market has a high ltv and significant slippage occurs.

## Proof of Concept

No PoC provided.

## Recommendation

Consider using the wFlow from the vault in this case.
