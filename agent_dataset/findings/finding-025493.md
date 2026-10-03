---
id: 25493
severity: "Low/Info"
---

# authorized mapping is not required if the indexes mapping stores the indexes + 1

## Description

BRC20Factory and Vault store the signers array, the authorized and indexes mapping. The authorized mapping can be removed if the indexes mapping stores index + 1 instead, so the check for existing signers can be made as indexes[signer] != 0.

## Proof of Concept

No PoC provided.

## Recommendation

Delete the authorized mapping, store the index as index + 1 in the indexes mapping and check if the signer exists by doing indexes[signer] != 0.
