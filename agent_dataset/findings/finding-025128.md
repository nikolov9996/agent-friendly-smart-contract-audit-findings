---
id: 25128
severity: "Low/Info"
---

# Deadline in Ole swap could be sent as a parameter to further prevent MEV

## Description

The deadline parameter to swap Ole is block.timestamp, so there is some room for MEV, although this is technically not possible on Blast as there is not a public mempool.

## Proof of Concept

No PoC provided.

## Recommendation

Send the deadline as a parameter.
