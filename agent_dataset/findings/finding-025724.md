---
id: 25724
severity: "Low/Info"
---

# Use of abi.encodePacked() with Dynamic Types

## Description

Using abi.encodePacked() with dynamic types, as seen in Verifier.sol on [L160](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/Verifier.sol#L160>) and in Endpoint.sol on [L749](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/50601071fb44010524ce4d667c5c881af1b2533e/contracts/Endpoint.sol#L749>), isn't advisable when feeding the outcome into a hashing function like keccak256(), due to [hash collisions](<https://scsfg.io/hackers/abi-hash-collisions/>).

## Proof of Concept

No PoC provided.

## Recommendation

Use abi.encode() instead.
