---
id: 25339
severity: "Low/Info"
---

# Attackers can DoS redemptions by cancelling requests just before the batch is processed

## Description



## Proof of Concept

## Vulnerability Detail

1. User creates a request.
2. User quickly removes the request, frontrunning the `processRedemptions()` call.

## Impact

Temporary DoS, but not feasible for an attacker, pure griefing. There may be some economical benefits to stop users withdrawals, but it is theoretical.

## Code Snippet

[https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R119](<https://github.com/sherlock-audit/2025-10-maple-oct-22nd/pull/11/files#diff-18c2378be607a98c91191fcd085ea891f37c1a8a9210c32f7aa3caa044c30550R119>)

## Recommendation

Consider skipping the request if it has been removed.
