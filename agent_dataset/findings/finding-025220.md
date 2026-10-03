---
id: 25220
severity: "Low/Info"
---

# Rounding error in Aave Lending Pool

## Description



## Proof of Concept

## Vulnerability Detail

These errors were found to be negligible, being at most 1 wei, and they can either increase or decrease `totalAssets()` by 1. It shouldn't be exploitable but it's good to know.

## Impact

`totalPrincipal` will be under/overestimated by 1 wei. For example, earning 1000 in `PreDepositVault::earn()`:

1. If it rounds up, `totalPrincipal` is 1000 but there will already be 1 profit, as we get 1001 aTokens
2. If it rounds down, `totalPrincipal` is 1000 but we only have 999 aTokens. Due to decimals in the assets, this isn't impactful. 1 wei is at most `1e-8` wbtc.

## Code Snippet

[https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L56-L62](<https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L56-L62>)

## Recommendation

Rounding error is very small so no fix is needed.
