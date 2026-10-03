---
id: 25609
severity: "Low/Info"
---

# MerkleTreeOperator::getMerklePath() will revert due to OOG after enough elements

## Description

MerkleTreeOperator::getMerklePath() [searches](<https://github.com/portalgateme/darkpool-v1-zk-contracts-fork/blob/master/contracts/core/MerkleTreeOperator.sol#L146-L151>) the tree in linear time for the index of the requested _noteCommitment.

Thus, it will run out of gas or timeout when using rpc providers when enough leaves are added.

## Proof of Concept

No PoC provided.

## Recommendation

Store the index of each leaf in a mapping.
