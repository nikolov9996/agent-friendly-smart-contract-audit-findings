---
id: 25689
severity: "Low/Info"
---

# ClampLib::mulDivUpInverse overflows on large target, DoSing SELL offer reads

## Description



## Proof of Concept

## Vulnerability Detail

The [helper](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L244-L246>):

```solidity
function mulDivUpInverse(uint256 target, uint256 den, uint256 num) internal pure returns (uint256) {
    return target.mulDivDown(den, num);
}
```

`getOfferRemaining` calls this with `target = remainingAssets` (derived from `offer.maxAssets`) and `den = WAD = 1e18` for SELL offers:

```solidity
uint256 units =
    offer.buy ? mulDivDownInverse(remainingAssets, WAD, price) : mulDivUpInverse(remainingAssets, WAD, price);
```

`offer.maxAssets` is a `uint256` chosen by the maker. Any value above `~1.16e59` (`type(uint256).max / 1e18`) overflows inside `mulDivDown`, reverting the entire `getOfferRemaining` call. `mulDivDownInverse` handles the symmetric situation gracefully by returning `type(uint256).max` and capping further via `UtilsLib.min(units, type(uint128).max)`, but `mulDivUpInverse` does not.

A SELL offer maker who sets `offer.maxAssets` above this threshold (or `type(uint256).max` as an "unbounded" sentinel) DoSes any path that reads remaining capacity for the offer.

## Impact

SELL offers with sufficiently large `maxAssets` revert on any clamp read, breaking the router's clamp path and any external integration that calls `getOfferRemaining` for the offer.

## Code Snippet

[https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L245](<https://github.com/sherlock-audit/2026-05-tenor-markets-may-21st-2026/blob/main/tenor-morpho-v2-contracts-2/src/periphery/libraries/ClampLib.sol#L245>)

## Recommendation

Mirror the guard from `mulDivDownInverse`:

```solidity
function mulDivUpInverse(uint256 target, uint256 den, uint256 num) internal pure returns (uint256) {
    if (target == 0) return 0;
    if (den > type(uint256).max / target) return type(uint256).max;
    return target.mulDivDown(den, num);
}
```
