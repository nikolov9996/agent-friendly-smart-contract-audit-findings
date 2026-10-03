---
id: 25363
severity: "Low/Info"
---

# Deadline parameter in SyrupUserActions::_swapViaBalancer() could be set to minimize MEV

## Description

SyrupUserActions sets a minimum amount out limit to prevent excessive MEV. However, as the deadline parameter is set to `block.timestamp` there is still some room for MEV.

## Proof of Concept

No PoC provided.

## Recommendation

Send a deadline parameter instead of hardcoding 0 to further mitigate MEV.
