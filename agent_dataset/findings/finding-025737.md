---
id: 25737
severity: "Low/Info"
---

# PerpEngineLp::burnLp() and SpotEngineLp::burnLp() are missing slippage checks

## Description

PerpEngineLp::burnLp() and SpotEngineLp::burnLp() have no slippage control parameters, which means that a user could get base and quote at a worse price/quantity than expected. The severity in Vertex is lower as transactions have to go through a delay or the sequencer, which makes it much harder to do MEV. In any case, the issue persists.

## Proof of Concept

No PoC provided.

## Recommendation

Include minimum quote and base parameters in the burnLp() functions.
