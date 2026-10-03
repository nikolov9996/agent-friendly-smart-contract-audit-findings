---
id: 25630
severity: "Low/Info"
---

# MetavaultsRegistry::removeBridgePathByIndex() is missing

## Description



## Proof of Concept

## Vulnerability Detail

All other functions to remove data have a "by index" counterpart, but `MetavaultsRegistry::removeBridgePath()` doesn't.

## Impact

Possible DoS.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R296](<https://github.com/sherlock-audit/2025-12-spectra-metavault-update-dec-16th/pull/2/files#diff-d6dbd850708b46c46f64d8bc2d13e4fe2de6f7ac75f0981bf638274c7830a293R296>)

## Recommendation

Add the "by index" equivalent.
