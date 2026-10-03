---
id: 25567
severity: "Medium"
---

# Estimated prize draws in TieredLiquidityDistributor are off due to rounding down when calculating the sum, leading to incorrect prizes

## Description



## Proof of Concept

## Vulnerability Detail

`ESTIMATED_PRIZES_PER_DRAW_FOR_5_TIERS` and the other tiers are precomputed initially in `TieredLiquidityDistributor::_sumTierPrizeCounts()`. In [here](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/abstract/TieredLiquidityDistributor.sol#L574>), it goes through all tiers and calculates the expected prize count per draw for each tier. However, when doing this [calculation](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/libraries/TierCalculationLib.sol#L113-L115>) in `TierCalculationLib.tierPrizeCountPerDraw()`, `uint32(uint256(unwrap(sd(int256(prizeCount(_tier))).mul(_odds))));`, it rounds down the prize count of each tier. This will lead to an incorrect prize count calculation, for example:

```solidity
grandPrizePeriodDraws == 8 days
numTiers == 5
prizeCount(tier 0) == 4**0 * 1 / 8 == 1 * 1 / 8 == 0.125 = 0
prizeCount(tier 1) == 4**1 * (1 / 8)^sqrt((1 + 1 - 3) / (1 - 3)) == 4 * 0.2298364718 ≃ 0.92 = 0
prizeCount(tier 2) == 4**2 * 1 == 16
prizeCount(tier 3) == 4**3 * 1 == 64
total = 80
```

However, if we multiply the prize counts by a constant and then divide the sum in the end, the total count would be 81 instead, getting an error of 1 / 81 ≃ 1.12 %

## Impact

The estimated prize count will be off, which affects the calculation of the next number of tiers in [PrizePool::computeNextNumberOfTiers()](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L472>). This modifies the whole rewards distribution for the next draw.

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/abstract/TieredLiquidityDistributor.sol#L574](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/abstract/TieredLiquidityDistributor.sol#L574>) [https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/libraries/TierCalculationLib.sol#L113-L115](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/libraries/TierCalculationLib.sol#L113-L115>)

## Recommendation

Add some precision to the calculations by multiplying, for example, by `1e5` each count and then dividing the sum by `1e5`. `uint32(uint256(unwrap(sd(int256(prizeCount(_tier)*1e5)).mul(_odds))));` and `return prizeCount / 1e5;`.
