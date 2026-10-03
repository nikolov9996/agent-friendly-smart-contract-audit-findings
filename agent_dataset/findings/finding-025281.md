---
id: 25281
severity: "Low/Info"
---

# EIP712's _revertIfError should use all SignatureChecker.Error errors

## Description

Function [ERC712._revertIfError](<https://github.com/MZero-Labs/common/blob/4a37119f2da946c6d8ad7b9a70dfdd219225115b/src/ERC712.sol#L150-L157>) goes through the different error possibilities in SignatureChecker.Error and raises the right error accordingly. But some are missing: InvalidSignatureS and InvalidSignatureV.

## Proof of Concept

No PoC provided.

## Recommendation

Consider either using the missing ones for better error messaging instead of raising the more general InvalidSignature error, or removing the unused ones from the enum.
