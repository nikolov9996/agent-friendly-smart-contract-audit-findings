---
id: 25600
severity: "Low/Info"
---

# Checks effects interactions pattern is not always followed

## Description

In StakingAssetManager::unlock(), fees are forwarded before marking the nullifier as used by calling _postWithdraw(). Although this is not exploitable because the call is permissioned by the relayer and it's not possible to register the same nullifier more than once, the pattern should always be followed to prevent future issues (if the code changes).

## Proof of Concept

No PoC provided.

## Recommendation

Forward the fees after recording all state changes.
