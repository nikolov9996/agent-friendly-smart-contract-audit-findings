---
id: 25012
severity: "Medium"
---

# DOS on liquidation type 1 due to underflow in cds profits computation

## Description



## Proof of Concept

See attack path

## Impact

Interruption of liquidation type 1 process. The loan is not liquidatable.

## Recommendation

Revise the computation of cds profits, it should not revert in any way possible so the liquidation won't be interrupted.
