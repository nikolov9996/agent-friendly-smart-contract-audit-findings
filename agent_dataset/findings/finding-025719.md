---
id: 25719
severity: "Low/Info"
---

# Usd0PP.sol::_deconstruct() is always called with msg.sender despite having receiver arguments

## Description



## Proof of Concept

## Vulnerability Detail

The function is defined as `function _deconstruct(uint256 amountUsd0, address bAssetRecipient, address rAssetRecipient)`, but in the code only `Usd0PP.sol::mint()` and `Usd0PP.sol::mintWithPermit()` are exposed, and they don't allow to specify different recipients, so the functionality is not fully implemented.

## Impact

Missing functionality.

## Code Snippet

[https://github.com/sherlock-audit/2025-11-usual-usd0-upgrade-nov-11th/blob/main/core-protocol/src/token/Usd0PP.sol#L226-L239](<https://github.com/sherlock-audit/2025-11-usual-usd0-upgrade-nov-11th/blob/main/core-protocol/src/token/Usd0PP.sol#L226-L239>)

## Recommendation

Add separate mint functions that allow receivers other than `msg.sender`.
