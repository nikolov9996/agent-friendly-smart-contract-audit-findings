---
id: 25175
severity: "Low/Info"
---

# executeFailedWithUpdatedArgs(...) shouldn't be able to change beneficiary

## Description

When the ConnextRouter message fails, it records the message in the ConnextHandler and sends it the funds. In the ConnextHandler, it's possible to change the actions and arguments of a failed tx in executeFailedWithUpdatedArgs(...).

Thus, it's possible to change the beneficiary, which would leave room for attacks to steal assets.

## Proof of Concept

No PoC provided.

## Recommendation

Check the beneficiary of the first action to match the previous beneficiary.
