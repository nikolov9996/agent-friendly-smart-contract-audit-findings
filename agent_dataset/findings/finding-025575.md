---
id: 25575
severity: "Medium"
---

# Witnet is not available on some networks listed

## Description



## Proof of Concept

## Vulnerability Detail

The sponsor intends to know concerns when deploying the protocol to the list of blockchains in the [readme](<https://audits.sherlock.xyz/contests/225>).

> We're interested to know if there will be any issues deploying the code as-is to any of these chains

One of these issues is that Witnet is not supported on Blast, Linea, ZkSync or Zerion, so an alternative rng source must be used.

Prize vaults may still be deployed, accruing yield and sending it to the prize pool, but the prize pool will not be able to award draws and will only refund users when it shutdowns.

## Impact

DoSed yield until the prize pool shutdown mechanism starts after the timeout.

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L938](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L938>) [https://docs.witnet.io/smart-contracts/supported-chains](<https://docs.witnet.io/smart-contracts/supported-chains>)

## Recommendation

Use an alternative RNG source on the non supported chains.
