---
id: 25241
severity: "Crit/High"
---

# totalReserves should be fetched from the strategies individually and summed up in the ReservePool

## Description

Currently totalReserves is updated based on deposits and withdrawal amounts to the reservePool. This means that rewards accrued in the strategies will not be accounted for, effectively not earning any yield.

In the case of AaveV3, the rewards from the RewardsController are separate from the accrued yield from supplying, so only the former would be accounted for.

## Proof of Concept

No PoC provided.

## Recommendation

totalReserves should be fetched individually from each strategy and summed up. One way to achieve this is by changing totalReserves() in ReservePool to fetch balances from all strategies . And in the AaveV3Strategy there should be a function getBalance() that takes into account the yield accrued.
