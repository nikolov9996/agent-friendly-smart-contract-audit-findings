---
id: 25449
severity: "Low/Info"
---

# Performance and management fees could round up to protect the protocol

## Description



## Proof of Concept

## Vulnerability Detail

Since the Vault uses a decimal offset to always have 18 decimals, the difference should be negligible, but it is something to keep in mind, especially as gas prices keep decreasing and $WBTC price keeps increasing. For this reason protocols often round up when calculating fees, though it may not be necessary in this case.

## Impact

Wei interest loss.

## Code Snippet

[https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R589-R596](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R589-R596>)

## Recommendation

Consider rounding up, though the impact is negligible here.
