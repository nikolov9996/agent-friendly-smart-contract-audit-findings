---
id: 25403
severity: "Low/Info"
---

# Cap::setEpochCap() may add a stale cap

## Description

Cap::setEpochCap() reverts when nextCap < $.cap[i], allowing the next cap to be equal to the current cap, which does not seem intended according to the error reason 'cap should be greater than previous cap'.

## Proof of Concept

No PoC provided.

## Recommendation

Replace the inequality check with less or equal to.
