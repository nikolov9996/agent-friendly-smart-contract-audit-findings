---
id: 25451
severity: "Medium"
---

# VaultV2::withdraw/redeem() are vulnerable to slippage, so another function could be added to protect users

## Description



## Proof of Concept

## Vulnerability Detail

The underlying adapters can register losses, which would be socialized among users of the VaultV2. In case one of them decides to withdraw or redeem and be frontrunned by one of these losses, they would receive a surprisingly lower amount of assets, incurring losses.

## Impact

User loss on withdrawal.

## Code Snippet

[https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R701-R714](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/25/files#diff-b9b86210e027003894f79227889d79167f92c0aa2b2a1b0291f4606002e22540R701-R714>)

## Recommendation

Add a function or router that includes slippage protection.
