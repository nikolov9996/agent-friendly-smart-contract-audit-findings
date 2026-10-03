---
id: 25753
severity: "Crit/High"
---

# Base calculation in Leverager::isLiquidateable() is incorrect as the max leverage may be smaller

## Description



## Proof of Concept

If `maxLevTimes` < `vp.maxTimesLeverage`, it means the base calculation would have in the divisor a bigger number than it should, so base will be smaller. As base is smaller, the collateral of the user can decrease more without the user being liquidated.

## Recommendation

Compare the 2 max leverage values and use the smallest, which is the actual maximum leverage allowed in the `Leverager`.
