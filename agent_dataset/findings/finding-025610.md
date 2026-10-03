---
id: 25610
severity: "Crit/High"
---

# MerkleRoot is not validated in all StakingAssetManager functions

## Description

All functions that require a merkle root to verify note inclusion must validate that the merkle root is valid. Otherwise, attackers can forge a merkle root that includes a fake note and steal all assets.

## Proof of Concept

No PoC provided.

## Recommendation

Validate that the provided Merkle Root is valid.
