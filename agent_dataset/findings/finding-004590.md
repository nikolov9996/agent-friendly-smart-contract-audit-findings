---
id: 4590
severity: "High"
---

# Incorrect tick calculation leads to DoS Submitted by etherhood

## Description

Assuming isToken0 is true. In Doppler, in rebalance function, currentTick is calculated as follows:
```solidity
currentTick =
_alignComputedTickWithTickSpacing(adjustmentTick + (accumulatorDelta / I_WAD).toInt24(), key.tickSpacing);
```
and to calculate tickLower and tickUpper:
```solidity
(int24 tickLower, int24 tickUpper) = _getTicksBasedOnState(newAccumulator, key.tickSpacing);
```
This might look okay, but there is an issue in this construction, accumulatorDelta is much smaller than newAccumulator which is sum of all accumulatorDelta calculated in previous calls. This results in currentTick being higher than tickLower. In lowerSlug, tickLower is upperTick and currentTick is lowerTick, this inconsistency cause an error while doing modifyLiquidity call for updating the LP positions, thus not allowing anymore swaps by its construction, till sale period ends in which users can sell assets back for numeraire token.

## Proof of Concept

This test fails for next swap because of the above issue, this fails during swap 3.
```solidity
function test_doppler_dos() public {
    uint256 numPDSlugs = hook.getNumPDSlugs();
    uint256 timeDelta = hook.getEndingTime() - hook.getStartingTime();
    vm.warp(hook.getStartingTime());
    buyExactIn(hook.getMinimumProceeds()/5);
    console2.log("Swap 1");
    vm.roll(block.number + 1);
    vm.warp(hook.getStartingTime() + timeDelta/5);
    buyExactIn(hook.getMinimumProceeds()*2/5);
    vm.roll(block.number + 1);
    vm.warp(hook.getStartingTime() + timeDelta*2/5);
    console2.log("Swap 2");
    buyExactIn(hook.getMinimumProceeds());
    vm.roll(block.number + 1);
    vm.warp(hook.getStartingTime() + timeDelta*3/5);
    console2.log("Swap 3");
}
```
Here is the log of ticks for each slug.
----------------
Lower Slug
tickLower -67128
tickUpper -67136
----------------
Upper Slug
tickLower -67136
tickUpper -67128
----------------
PD Slug
tickLower -67128
tickUpper -66864
----------------
PD Slug
tickLower -66864
tickUpper -66600
----------------
PD Slug
tickLower -66600
tickUpper -66336
It is clear ticks in Lower Slug are inconsistent as compared to others.

## Recommendation

The solution is not clear, root cause lies in either _getMaxTickDeltaPerEpoch:
```solidity
return int256(endingTick - effectiveStartingTick) * I_WAD / int256((endingTime - startingTime) / epochLength);
```
Because it keeps on returning increasing values of accumulatorDelta, which is accumulated in newAccumulate, or in:
```solidity
currentTick =
_alignComputedTickWithTickSpacing(adjustmentTick + (accumulatorDelta / I_WAD).toInt24(), key.tickSpacing);
(int24 tickLower, int24 tickUpper) = _getTicksBasedOnState(newAccumulator, key.tickSpacing);
```
Which is then used in calculation of tickLower, unlike currentTick which only use accumularDelta. Thus reducing tickLower more than currentTick.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical error in the way the Doppler contract computes price ticks during a rebalance operation. The contract derives the current tick from a small incremental value called accumulatorDelta, while the lower and upper bounds of the tick range (tickLower and tickUpper) are calculated from a cumulative accumulator that aggregates all previous deltas. Because the cumulative value grows much faster than the single‑step delta, the computed currentTick can become larger than tickLower. This mismatch violates the invariant that the current tick must lie within the tick range used for liquidity positions. When the contract later calls modifyLiquidity with the inconsistent tick values, the call reverts, preventing any further liquidity updates or swaps. The impact is a denial‑of‑service condition: after a few successful swaps (the third swap in the provided test), all subsequent swap attempts fail, users see transaction reverts or “no output”, and the protocol’s market becomes frozen until the sale period ends and the contract resets. The issue occurs only after enough swaps have accumulated enough delta to expose the divergence, making it hard to notice during early testing. It affects every participant who tries to trade or provide liquidity, effectively locking funds in the pool for the duration of the outage. The problem was discovered by an automated unit test that exercised multiple swaps and logged the tick values, revealing that the lower slug’s tickLower was higher than the current tick, a condition that should never happen. The bug belongs to the class of accounting‑state mismatches where cumulative and incremental state variables are mixed inconsistently, leading to invariant violations. To fix the issue, the tick calculation must be unified: either compute both currentTick and tickLower from the same accumulator source, or adjust the helper that derives tick bounds so that it respects the same delta scaling as the current tick. Ensuring that tickLower is never greater than currentTick restores the ability to modify liquidity and prevents the DoS scenario. From a user perspective, the symptom is that a swap transaction suddenly reverts with no token transfer, contrary to the expectation that the swap would succeed and the user would receive the exchanged asset. This break in business logic contradicts the protocol’s guarantee of continuous market operation and can lead to loss of confidence and potential financial loss for liquidity providers.
