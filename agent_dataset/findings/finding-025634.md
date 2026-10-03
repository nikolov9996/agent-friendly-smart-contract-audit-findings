---
id: 25634
severity: "Low/Info"
---

# MetavaultsRegistry::registerMarket()/allowBridgePath() duplicate onlyRegistered modifier

## Description



## Proof of Concept

## Vulnerability Detail

`MetavaultsRegistry::onlyRegistered()` modifier is present on both the external functions and internal ones.

## Impact

Gas usage.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R149](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R149>)

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R271](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R271>)

## Recommendation

Keep the modifier only in the internal functions. Don't do this for the restricted modifier though, that one needs to be on the external function.
