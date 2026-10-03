---
id: 25218
severity: "Medium"
---

# PreDepositVault does not collect interest for WBTC

## Description



## Proof of Concept

## Vulnerability Detail

See the market here for details [https://app.aave.com/reserve-overview/?underlyingAsset=0x2260fac5e5542a773aa44fbcfedf7c193bc2c599&marketName=proto_mainnet](<https://app.aave.com/reserve-overview/?underlyingAsset=0x2260fac5e5542a773aa44fbcfedf7c193bc2c599&amp;marketName=proto_mainnet>)

## Impact

No profit collection for WBTC

## Code Snippet

[https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L12](<https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L12>)

## Recommendation

Use an alternative yield source.
