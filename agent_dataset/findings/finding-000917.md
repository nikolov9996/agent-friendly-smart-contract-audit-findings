---
id: 917
severity: "High"
---

# ConcentratedLiquidityPool: incorrect `feeGrowthGlobal` accounting when crossing ticks

## Description

Swap fees are taken from the output. Hence, if swapping token0 for token1 (`zeroForOne` is true), then fees are taken in token1. We see this to be the case in the initialization of `feeGrowthGlobal` in the swap cache

```solidity
feeGrowthGlobal = zeroForOne ? feeGrowthGlobal1 : feeGrowthGlobal0;
```

and in `_updateFees()`.

However, looking at `Ticks.cross()`, the logic is the reverse, which causes wrong fee accounting.

```solidity
if (zeroForOne) {
	...
	ticks[nextTickToCross].feeGrowthOutside0 = feeGrowthGlobal - ticks[nextTickToCross].feeGrowthOutside0;
} else {
	...
	ticks[nextTickToCross].feeGrowthOutside1 = feeGrowthGlobal - ticks[nextTickToCross].feeGrowthOutside1;
}
```

## Proof of Concept

no poc

## Recommendation

Switch the `0` and `1` in `Ticks.cross()`.

```solidity
if (zeroForOne) {
	...
	// `feeGrowthGlobal` = feeGrowthGlobal1
	ticks[nextTickToCross].feeGrowthOutside1 = feeGrowthGlobal - ticks[nextTickToCross].feeGrowthOutside1;
} else {
	...
	// feeGrowthGlobal = feeGrowthGlobal0
	ticks[nextTickToCross].feeGrowthOutside0 = feeGrowthGlobal - ticks[nextTickToCross].feeGrowthOutside0;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the way the ConcentratedLiquidityPool contract records fee growth when a swap operation crosses a price tick. In a swap where token0 is exchanged for token1 (zeroForOne is true), the protocol correctly deducts fees from the output token1 and stores the cumulative fee amount in the global variable feeGrowthGlobal1. Conversely, when swapping in the opposite direction, fees are taken from token0 and stored in feeGrowthGlobal0. The root cause of the issue is a mismatch in the fee accounting logic inside the Ticks.cross() function: the implementation mistakenly updates feeGrowthOutside0 when zeroForOne is true and feeGrowthOutside1 when zeroForOne is false, effectively using the opposite token’s fee growth reference. This inversion causes the per‑tick fee snapshots to be calculated with the wrong fee growth index, leading to inaccurate fee attribution for liquidity providers whose positions span the crossed tick. Exploitation does not require a malicious actor; any legitimate swap that triggers a tick crossing will produce erroneous fee accounting. As a result, liquidity providers may receive less (or more) fee revenue than entitled, and the protocol’s accounting invariants break, potentially causing a mismatch between the total fees collected and the sum of fees distributed, which can manifest to users as missing refunds, balances that appear to shrink unexpectedly, or “funds disappearing” from the pool. The condition occurs whenever a swap traverses a tick boundary—specifically, any swap that changes the price enough to cross the next initialized tick. All participants in the pool, including traders, liquidity providers, and the protocol itself, are affected because the fee distribution logic is central to the economic model. The issue was uncovered during a systematic audit by Code4rena, where the auditors compared the initialization of feeGrowthGlobal with the update logic in Ticks.cross() and observed the reversed token indices. The bug is subtle because the contract’s external behavior (swap execution) still succeeds, and the fee discrepancy may only become apparent after many swaps or when reviewing detailed fee accounting reports, making it easy to miss during surface‑level testing. To remediate the problem, the feeGrowthOutside update in Ticks.cross() should reference the same token index as feeGrowthGlobal—i.e., when zeroForOne is true, update feeGrowthOutside1 using feeGrowthGlobal1, and when false, update feeGrowthOutside0 using feeGrowthGlobal0. This correction aligns the per‑tick fee snapshot with the global fee growth used for fee calculation, restoring proper fee distribution and preserving the protocol’s accounting guarantees.
