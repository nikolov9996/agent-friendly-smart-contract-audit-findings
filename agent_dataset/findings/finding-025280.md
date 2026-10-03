---
id: 25280
severity: "Low/Info"
---

# Some contracts don't implement their entire interface

## Description

There are some contracts that don't fully implement the interface with the same name. For example, [IERC5805](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/abstract/interfaces/IERC5805.sol>) defines functions such as delegates, getPastVotes and getVotes.

These functions are not implemented in ERC5805, only in EpochBasedVoteToken.

## Proof of Concept

No PoC provided.

## Recommendation

Implement all interface functions in the contract with the same name, even if said implementation remains empty and virtual.
