---
id: 25448
severity: "Low/Info"
---

# Performance and management fee updates may technically still apply to already earned interest

## Description



## Proof of Concept

## Vulnerability Detail

`VaultV2::setPerformanceFee()` correctly accrues interest first, and only changes the fee afterwards, [link](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R398-R403>). However, note that the interest accrued is capped by the max rate, [link](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R584>). This means that the pending interest earned while the old rate was active will be now applied the new rate.

## Impact

Under/over charging fees.

## Code Snippet

[https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R406](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R406>)

[https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R584](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R584>)

## Recommendation

There are ways to fix this but not quite trivial.
