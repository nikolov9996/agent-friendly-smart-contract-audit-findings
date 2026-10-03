---
id: 25752
severity: "Medium"
---

# ReserveLogic::_updateIndexes() assumes the utilization rate was constant the whole time when calculating the new borrows

## Description



## Proof of Concept

Borrow interest depends on the utilization rate. The utilization rate grows with borrows, so it can not stay constant when calculating the new borrows over time.

## Recommendation

Implement a closed formula that calculates the new borrows and utilization rate correctly.
