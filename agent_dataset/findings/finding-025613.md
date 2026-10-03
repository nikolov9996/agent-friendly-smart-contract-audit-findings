---
id: 25613
severity: "Crit/High"
---

# Reusing the same rho and pubKey in different deposits leads to lost tokens

## Description

The [nullifier](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/circuits/fuzk/src/lib.nr#L106-L113>) is formed from rho and the schnorr pubKey.

This means that depositing with different assets and amounts will still have the same nullifier, leading to the inability to move the following deposits with the same rho and pubKey. Check the poc [here](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/commit/cfa1fc63fc2258eb2db18df687db8b9b184bd8cf>) for details.

## Proof of Concept

No PoC provided.

## Recommendation

Either enforce the nullifier uniqueness (via unique rho and pubkey combination) or use the note as nullifier.
