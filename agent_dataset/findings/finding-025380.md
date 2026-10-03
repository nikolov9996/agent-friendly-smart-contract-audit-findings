---
id: 25380
severity: "Low/Info"
---

# Hardcoded variables should be placed as constants

## Description

The [LzEndpoint](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L48>), a [minter](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L55>), the royalty [fee](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L53>) and the pay in zero flags [([1]](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L108>), [[2])](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L152>) are hardcoded values, but should be placed as constants instead.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
