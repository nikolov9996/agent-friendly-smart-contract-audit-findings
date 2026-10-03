---
id: 25636
severity: "Low/Info"
---

# Some variable shadowing in MetavaultsRegistry

## Description



## Proof of Concept

## Vulnerability Detail

Market and chainConfig are used throughout the contract as memory variable, but there already exist functions with these names.

## Impact

QA

## Code Snippet

For example, [market](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R148>) and [market()](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R527>).

## Recommendation

Consider changing the variable or function names.
