---
id: 25382
severity: "Medium"
---

# Can not mint 1000 tokens, only 999

## Description

Only 999 tokens can be limited according to the [code](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L17>), but the comments indicated that 1000 tokens should be minted on genesis. See the [POC](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/test/test.t.sol#L25>) for confirmation.

## Proof of Concept

No PoC provided.

## Recommendation

Change [genesisCounter](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L19>) to 0.
