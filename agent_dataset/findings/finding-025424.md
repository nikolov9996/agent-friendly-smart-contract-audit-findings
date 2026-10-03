---
id: 25424
severity: "Low/Info"
---

# BasicVault::getRedeemRequestOf() will revert as the redeem requests are filled with the wrong indexes

## Description

In BasicVault::getRedeemRequestOf(), redeemRequests is filled with the requests from the queue from the IndexByRequestor struct offset, which stores the last non resolved request. In the loop where redeemRequests is assigned, it does redeemRequests[i] = ..., but i starts at from, which may not be 0 and revert in this case.

## Proof of Concept

No PoC provided.

## Recommendation

Replace the code to redeemRequests[i - from] = ....
