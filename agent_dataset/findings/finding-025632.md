---
id: 25632
severity: "Low/Info"
---

# Possible mistake in the unregister by index functions

## Description



## Proof of Concept

## Vulnerability Detail

As `MetavaultsRegistry::unregisterMarketByIndex()` doesn't check the market, if 2 calls are made consecutively, they may arrive at the blockchain in different order, and remove the wrong markets (array popping changes order).

## Code Snippet

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R187](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R187>)

## Recommendation

Send the expected market as argument to verify.
