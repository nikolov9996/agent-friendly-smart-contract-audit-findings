---
id: 25430
severity: "Low/Info"
---

# Approval is not reset to 0 after approving the markets for wFlow assets repayment in LoopStrategy::onMoreFlashLoan()

## Description

LoopStrategy::onMoreFlashLoan() does not reset the approval of the markets to 0 after approving the repayment of wFlow.

## Proof of Concept

No PoC provided.

## Recommendation

This is not a problem for wFlow, but some tokens revert when approving from a null amount to a non null amount, so consider resetting the approval.
