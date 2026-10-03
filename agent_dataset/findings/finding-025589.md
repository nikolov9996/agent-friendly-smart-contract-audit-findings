---
id: 25589
severity: "Low/Info"
---

# Setting note commitments, nullifiers and note footers used should revert if they are already set to prevent exploits

## Description

Setting note commitments, nullifiers and note footers should never happen after they are already set, in which case the transaction should revert, as it is some clear attempt of an exploit.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if they are already set.
