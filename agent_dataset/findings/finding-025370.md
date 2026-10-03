---
id: 25370
severity: "Low/Info"
---

# Hardcoded 1e18 in SyrupRateProvider

## Description

SyrupRateProvider hardcodes the shares when [calling](<https://github.com/maple-labs/syrup-router/blob/main/contracts/utils/SyrupRateProvider.sol#L17>) IPoolLike(pool).convertToExitAssets(1e18);.

## Proof of Concept

No PoC provided.

## Recommendation

Consider using a constant state value instead along with a comment for better readability.
