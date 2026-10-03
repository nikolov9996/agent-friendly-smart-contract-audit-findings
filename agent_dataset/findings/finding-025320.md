---
id: 25320
severity: "Low/Info"
---

# Consider adding a check to ensure that fees, delegate cover and so on have been explicitly set.

## Description

Some fees or delegate cover information are set in the globals. When fetched, there is no check that the values for a specific pool or loan manager have been set, so the default 0 value is assumed. This could lead to unexpected results, even more so if a pool is deployed through means other than the Maple frontend (or it does not behave as expected).

## Proof of Concept

No PoC provided.

## Recommendation

Create getters that check if the values were explicitly set, isSet[key].
