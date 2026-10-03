---
id: 25212
severity: "Low/Info"
---

# In ConnextHandler, executeFailedWithUpdatedArgs(...), the whole tx is updated on storage if the try call succeeds

## Description

In the ConnextHandle, executeFailedWithUpdatedArgs(...), the failed tx executed field is set to true. Currently it is loaded in memory and then written to storage completely, which is unnecessary and adds significant gas overhead.

## Proof of Concept

No PoC provided.

## Recommendation

Change the code below try connextRouter.xBundle(actions, args) to _failedTxns[transferId][nonce].executed = true; to save on storage writes.
