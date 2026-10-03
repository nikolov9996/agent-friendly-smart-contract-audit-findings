---
id: 25221
severity: "Low/Info"
---

# ATokens can be swept of the PreDepositVault

## Description



## Proof of Concept

## Vulnerability Detail

`PreDepositVault::totalAssets()` is composed of `asset()` and `aToken`. Decreasing one of them leads to user losses.

## Impact

User losses

## Code Snippet

[https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L86](<https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L86>)

## Recommendation

It's an admin function so could be left as is, but keep this in mind.
