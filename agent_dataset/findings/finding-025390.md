---
id: 25390
severity: "Crit/High"
---

# Send should revert if the gas limit has not been set for a destination chain (peer)

## Description

[send()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L98>) allows users to send messages with 0 gas limit if the gasLimit mapping has not be seen for a certain peer. This will likely make the transaction revert on the destination chain, losing the funds.

POC [here](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/test/test.t.sol#L93>).

## Proof of Concept

No PoC provided.

## Recommendation

Revert if trying to send a message to _dstEid whose gas limit was not yet set.
