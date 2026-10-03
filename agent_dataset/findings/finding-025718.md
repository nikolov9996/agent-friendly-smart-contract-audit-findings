---
id: 25718
severity: "Low/Info"
---

# Usd0PP::mintWithPermit() no longer checks that the timestamp exceeds the bond start

## Description



## Proof of Concept

## Vulnerability Detail

Most of the minting logic was moved to `Usd0PP::_deconstruct()`, but the timestamp and bond start check wasn't, and was kept only on the `mint()` function, having conflicting checks compared to `Usd0PP::mintWithPermit()`.

## Impact

No impact since at the moment the timestamp is bigger than the bond start and the check is useless, but a fresh deployment could make it problematic.

## Code Snippet

[https://github.com/sherlock-audit/2025-11-usual-usd0-upgrade-nov-11th/blob/main/core-protocol/src/token/Usd0PP.sol#L230-L240](<https://github.com/sherlock-audit/2025-11-usual-usd0-upgrade-nov-11th/blob/main/core-protocol/src/token/Usd0PP.sol#L230-L240>)

## Recommendation

Make the checks consistent across both functions.
