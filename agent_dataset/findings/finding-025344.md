---
id: 25344
severity: "Low/Info"
---

# SyrupBitcoinRouter::setAssetController() could always allow the asset controller to be set to 0

## Description



## Proof of Concept

## Vulnerability Detail

Other similar functions in the protocol allow setting a setting to 0, even if not whitelisted, so the same could apply in this situation. Since the function call is permissioned, it could make it smoother to just allow the asset controller to be set to address(0) regardless of the COMPOSITE_DEPOSIT_ASSET flag.

## Impact

Slightly more mistake prone, but it's still possible to first set the asset controller to 0 and then unwhitelist COMPOSITE_DEPOSIT_ASSET from Globals.

## Code Snippet

[https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R191](<https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R191>)

## Recommendation

Consider always allowing setting to address(0).
