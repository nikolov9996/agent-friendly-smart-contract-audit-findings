---
id: 25008
severity: "Medium"
---

# Accumulated profit/losses by the cumulative value is not dealt with in borrowingLiquidation::liquidationType1(), leading to losses

## Description



## Proof of Concept

See the calculations above.

## Impact

Cds depositor can never withdraw until the cumulative value recovers. Alternatively, consider that calculating the cumulative value before liquidation yields -0.2, but after liquidating yields -0 (totalVolumeOfBorrowersAmountinWei becomes 0, so the cumulative value loss is 0), which goes to show that effectively it is incorrectly handled. Any user can trigger cumulative value updates before liquidations to force this bug, if needed.

## Recommendation

Handle the cumulative values when liquidating.
