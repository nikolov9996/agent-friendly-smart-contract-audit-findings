---
id: 25687
severity: "Low/Info"
---

# ClampLib::mulDivDownInverse contains a dead n == 0 check

## Description



## Proof of Concept

## Vulnerability Detail

[Code](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L232-L237>):

```solidity
uint256 n = target + 1;
if (n == 0 || den > type(uint256).max / n) {
    return type(uint256).max;
}
```

`n == 0` looks like an intentional overflow guard, but with checked arithmetic the addition reverts before `n` becomes `0`. The check is misleading and obscures the real overflow case (see the sibling finding on `target + 1` overflowing).

## Impact

Confusing code.

## Code Snippet

[https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L234](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L234>)

## Recommendation

```solidity
if (target == type(uint256).max) return type(uint256).max;
uint256 n = target + 1;
if (den > type(uint256).max / n) return type(uint256).max;
```
