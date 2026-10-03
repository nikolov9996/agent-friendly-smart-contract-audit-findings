---
id: 25489
severity: "Low/Info"
---

# Hardcoded 1e18 ratio calculation regardless of decimals

## Description

MellowPriceFeed gets the ratio by doing answer = int256(uint256(ratiosX96[0])) * 1e18 / int256(managedRatiosOracle.Q96());, hardcoding the decimals to 1e18.

However, the decimals are set in the constructor and stored in priceFeedDecimals, and could differ from 1e18.

## Proof of Concept

No PoC provided.

## Recommendation

answer = int256(uint256(ratiosX96[0])) * 10**priceFeedDecimals / int256(managedRatiosOracle.Q96());
