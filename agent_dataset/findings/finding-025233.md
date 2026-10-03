---
id: 25233
severity: "Low/Info"
---

# Strategy percentages will differ over time as yield accrued differs in ReservePool

## Description

The ReservePool always deposits and withdraws according to the specified strategy weights. As the strategies have different yield rates, the actual weights will change over time.

## Proof of Concept

No PoC provided.

## Recommendation

To overcome this, a rebalance function could be added to the ReservePool that is called whenever the values differ too much or on every rebalance.
