---
id: 25125
severity: "Medium"
---

# createCommonProjectIDAndDeploymentRequest() hardcodes request id index to 0, leading to lost requests for users

## Description



## Proof of Concept

See above.

## Impact

First request is overwritten and one of them will not be finalized as `submitProofOfDeployment()` and `submitDeploymentRequest()` can only be called once as part of the final steps by the worker. However, the user paid fees for both requests, but only one of them will go through.

## Recommendation

Index should be increment in a user mapping.
