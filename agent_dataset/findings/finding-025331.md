---
id: 25331
severity: "Low/Info"
---

# In PoolManager, setOpenToPublic(), there is no way to unset openToPublic.

## Description

The setOpenToPublic(...) function only enables setting openToPublic to true, so if a delegate sets a permissioned pool to open by mistake, it's impossible to undo it.

## Proof of Concept

No PoC provided.

## Recommendation

Add setOpenToPublic as an argument.
