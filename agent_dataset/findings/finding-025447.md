---
id: 25447
severity: "Low/Info"
---

# A deallocateAll() function could be useful to successfully guarantee market removal in the Morpho market adapter

## Description



## Proof of Concept

## Vulnerability Detail

`MorphoMarketV1Adapter::updateList()` is called after every deallocation to remove the market from the list if the assets are null there. However, due to interest accrual, leftover dust may be left after deallocation, which may make it annoying to fully remove a market.

## Impact

Removing a market from the list can be delayed, which should just slightly affect gas costs.

## Code Snippet

[https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/6/files#diff-29a9f0002168ac012f2dbea176776275c39c841f56d6e756b80f663e491f236fR87](<https://github.com/sherlock-audit/2025-08-morpho-vault-v2-aug-13th/pull/6/files#diff-29a9f0002168ac012f2dbea176776275c39c841f56d6e756b80f663e491f236fR87>)

## Recommendation

Add a `deallocateAll()` function to forcefully remove all funds from the market.
