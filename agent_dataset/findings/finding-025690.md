---
id: 25690
severity: "Low/Info"
---

# ClampLib::mulDivDownInverse reverts on target == type(uint256).max before the overflow guard runs

## Description



## Proof of Concept

## Vulnerability Detail

The [function](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L232-L238>):

```solidity
function mulDivDownInverse(uint256 target, uint256 den, uint256 num) internal pure returns (uint256) {
    uint256 n = target + 1;
    if (n == 0 || den > type(uint256).max / n) {
        return type(uint256).max; // overflow -> this constraint is not the bottleneck
    }
    return (n * den - 1) / num;
}
```

With Solidity 0.8.x checked arithmetic, `target + 1` reverts when `target == type(uint256).max`. The guard immediately below is meant to handle the overflow case by returning `type(uint256).max`, but it never executes.

`getOfferRemaining` reaches this function with `remainingAssets` derived from `offer.maxAssets`, which is a `uint256` controlled by the maker. A maker setting `offer.maxAssets = type(uint256).max` (or any value such that `remainingAssets` equals `type(uint256).max`) DoSes any helper that calls `getOfferRemaining` for that offer, including the router's clamp logic.

## Impact

Callers reading offer state for a maker-controlled `offer.maxAssets == type(uint256).max` revert instead of receiving the documented "unbounded" sentinel, blocking offer reads and any clamp-based path that consumes them.

## Code Snippet

[https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L233](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L233>)

## Recommendation

Short-circuit before the addition:

```solidity
function mulDivDownInverse(uint256 target, uint256 den, uint256 num) internal pure returns (uint256) {
    if (target == type(uint256).max) return type(uint256).max;
    uint256 n = target + 1;
    if (den > type(uint256).max / n) {
        return type(uint256).max;
    }
    return (n * den - 1) / num;
}
```
