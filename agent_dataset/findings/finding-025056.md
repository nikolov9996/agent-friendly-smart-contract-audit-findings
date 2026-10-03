---
id: 25056
severity: "Low/Info"
---

# Rounds in IDOPoolAbstract::manageRoundToMetaIDO() can be overriden

## Description

`IDOPoolAbstract::manageRoundToMetaIDO()` does not check if `idoRoundClocks[roundId].parentMetaIdoId` has already been set, allowing it to be overriden and rounds to be linked to more than 1 `metaIDO` in the `metaIDO.roundIds` array. This has no impact as the `parentMetaIdoId` would be the latest one set to the `roundId`, but the arrays `metaIDO.roundIds` of several `metaIDO` could be polluted with the same `roundId`.

## Proof of Concept

No PoC provided.

## Recommendation

Consider checking that `idoRoundClocks[roundId].parentMetaIdoId == 0` when `addRound == true`.
