---
id: 25604
severity: "Low/Info"
---

# Missing event in VerifierHub::setVerifier()

## Description

[VerifierHub::setVerifier()](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/VerifierHub.sol#L56>) should emit an event when a verifier is set.

## Proof of Concept

No PoC provided.

## Recommendation

Emit events for all relevant state changes.
