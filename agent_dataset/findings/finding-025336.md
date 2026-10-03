---
id: 25336
severity: "Low/Info"
---

# SyrupBitcoinRouter::processRedemptions() could be optimized by batching transfers together

## Description



## Proof of Concept

## Vulnerability Detail

As can be seen [here](<https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R109>), it will transfer/redeem on every iteration, which is not very effective.

## Impact

N/A

## Code Snippet

[https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R109](<https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R109>)

## Recommendation

Redeeming, treasury fees, and even the owner could be optimized to be batched together.
