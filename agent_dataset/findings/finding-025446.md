---
id: 25446
severity: "Low/Info"
---

# Adapters could store the index instead of true in the VaultV2 to remove the O(n) search

## Description



## Proof of Concept

## Vulnerability Detail

The number of adapters is admin controlled so DoS should never happen due to OOG. However, it could not even be a concern in case the index of the adapter plus one (1) was stored in the mapping, such that no search was needed.

## Impact

Gas optimization and better security guarantees.

## Code Snippet

[https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R355](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R355>)

## Recommendation

Store the index plus one (1) in the mapping instead and use it to remove from the array.
