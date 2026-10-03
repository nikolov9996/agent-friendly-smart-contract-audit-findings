---
id: 25290
severity: "Low/Info"
---

# Missing override keyword for interface inherited methods

## Description

Most contracts are not implementing their interface methods with override keywords. For example, the [DistributionVault](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/DistributionVault.sol>) contract implements all its interface functions, but it doesn't add the override keyword to any of the functions.

This means the compiler won't check that the implementation is properly implementing what is defined on the interface, making it prone to spelling errors and function signature mismatching.

## Proof of Concept

No PoC provided.

## Recommendation

Add the override keyword to those contracts functions as a best practice and for compiler checks.
