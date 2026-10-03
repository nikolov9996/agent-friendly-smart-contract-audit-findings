---
id: 25264
severity: "Low/Info"
---

# KeyringCoreV2Base could use a 2 step admin transfer mechanism

## Description

Admin transfer in KeyringCoreV2Base is performed at once, possibly setting the admin to an incorrect address. To mitigate this risk, protocols usually implement a 2 step mechanism, where a pending admin is set who has to call acceptAdmin() in order for the admin to actually change. This ensures that the admin is always correctly set.

## Proof of Concept

No PoC provided.

## Recommendation

Implement the 2 step mechanism.
