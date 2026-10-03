---
id: 25499
severity: "Low/Info"
---

# Domain separator calculation is not fork safe

## Description

The domain separator is cached in the constructor of the [contracts](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/EIP712.sol#L80-L86>), which could lead to signature signing softwares in case of a hard fork.

When a hard fork happens, block.chainid changes, which affects the domain separator, but as it is only computed in the constructor, it will be forever incorrect. Messages can still be signed but EIP712 will be broken.

## Proof of Concept

No PoC provided.

## Recommendation

The EIP712 contract from OpenZeppelin handles this by caching the original domain separator and recomputing it if block.chainid has changed.
