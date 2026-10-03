---
id: 25743
severity: "Low/Info"
---

# Verifier::checkQuorum() returns false with more than 3 signers

## Description

The [signerBitmask](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/Endpoint.sol#L751>) is hardcoded to 7 when calling [requireValidSignature(),](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/Verifier.sol#L114>) meaning that [nSigned](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/Verifier.sol#L111>) would be incremented at most 3 times in [checkQuorum()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/Verifier.sol#L100>) as 7 = 00000111.

Consequently, if there are more than 3 signers added in the Verifier contract, Verifier::checkQuorum() will always return false in the following scenarios:

- nSigner >= 4 and nSigned <= 2
- nSigner >= 6 and nSigned <= 3

## Proof of Concept

No PoC provided.

## Recommendation

Make signerBitmask dynamic.
