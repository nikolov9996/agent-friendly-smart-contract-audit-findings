---
id: 25434
severity: "Low/Info"
---

# > should be used instead of!= in LoopStrategy::_deposit()

## Description

LoopStrategy::_deposit() stops iterating if the utilization ratio reaches exactly the target, that is, market.totalSupplyAssets.wMulDown(targetUtilization) == totalBorrowAssets.

However, if the utilization is bigger, it continues.

## Proof of Concept

No PoC provided.

## Recommendation

This should not be possible given the rest of the function, but using > is more correct.
