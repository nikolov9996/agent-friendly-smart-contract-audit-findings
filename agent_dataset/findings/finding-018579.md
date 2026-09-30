---
id: 18579
severity: "High"
---

# Second per liquidity inside could overflow `uint256` causing the LP position to be locked in `UniswapV3Staker`

## Description

`UniswapV3Staker` depends on the second per liquidity inside values from the `Uniswap V3 Pool` to calculate the amount of rewards a position should receive. This value represents the amount of second liquidity inside a tick range that is “active” (`tickLower < currentTick < tickUpper`). The second per liquidity inside a specific tick range is supposed to always increase over time.

In the `RewardMath` library, the seconds inside are calculated by taking the current timestamp value and subtracting the value at the moment the position is staked. Since this value increases over time, it should be normal. Additionally, this implementation is similar to [Uniswap Team’s implementation](https://github.com/Uniswap/v3-staker/blob/4328b957701de8bed83689aa22c32eda7928d5ab/contracts/libraries/RewardMath.sol#L35).
```solidity
function computeBoostedSecondsInsideX128(
    uint256 stakedDuration,
    uint128 liquidity,
    uint128 boostAmount,
    uint128 boostTotalSupply,
    uint160 secondsPerLiquidityInsideInitialX128,
    uint160 secondsPerLiquidityInsideX128
) internal pure returns (uint160 boostedSecondsInsideX128) {
    // this operation is safe, as the difference cannot be greater than 1/stake.liquidity
    uint160 secondsInsideX128 = (secondsPerLiquidityInsideX128 - secondsPerLiquidityInsideInitialX128) * liquidity;
    // @audit secondPerLiquidityInsideX128 could smaller than secondsPerLiquidityInsideInitialX128
    ...
}
```
However, even though the second per liquidity inside value increases over time, it could overflow `uint256`, resulting in the calculation reverting. When `computeBoostedSecondsInsideX128()` reverts, function `_unstake()` will also revert, locking the LP position in the contract forever.

## Proof of Concept

Consider the value of the second per liquidity in three different timestamps: `t1 < t2 < t3`
```solidity
secondPerLiquidity_t1 = -10 = 2**256-10
secondPerLiquidity_t2 = 100
secondPerLiquidity_t3 = 300
```
As we can see, its value always increases over time, but the initial value could be smaller than 0. When calculating `computeBoostedSecondsInsideX128()` for a period from `t1 -> t2`, it will revert.

Additionally, as I mentioned earlier, this implementation is similar to the one from Uniswap team. However, please note that the Uniswap team used Solidity 0.7, which won’t revert on overflow and the formula works as expected while Maia uses Solidity 0.8.

For more information on how a tick is initialized, please refer to [this code](https://github.com/Uniswap/v3-core/blob/d8b1c635c275d2a9450bd6a78f3fa2484fef73eb/contracts/libraries/Tick.sol#L132-L142)
```solidity
if (liquidityGrossBefore == 0) {
    // by convention, we assume that all growth before a tick was initialized happened _below_ the tick
    if (tick <= tickCurrent) {
        info.feeGrowthOutside0X128 = feeGrowthGlobal0X128;
        info.feeGrowthOutside1X128 = feeGrowthGlobal1X128;
        info.secondsPerLiquidityOutsideX128 = secondsPerLiquidityCumulativeX128;
        info.tickCumulativeOutside = tickCumulative;
        info.secondsOutside = time;
    }
    info.initialized = true;
}
```
The second per liquidity inside a range that has `tickLower < currentTick < tickUpper` is [calculated as](https://github.com/Uniswap/v3-core/blob/d8b1c635c275d2a9450bd6a78f3fa2484fef73eb/contracts/UniswapV3Pool.sol#L221):
```solidity
secondsPerLiquidityCumulativeX128 - tickLower.secondsPerLiquidityOutsideX128 - tickUpper.secondsPerLiquidityOutsideX128

// If lower tick is just init,
// Then: secondsPerLiquidityCumulativeX128 = tickLower.secondsPerLiquidityOutsideX128
// And: tickUpper.secondsPerLiquidityOutsideX128 != 0
// => Result will be overflow
```

## Recommendation

Consider using an `unchecked` block to calculate this value.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic overflow/underflow in the UniswapV3Staker contract when it calculates the boosted seconds that a liquidity position has been active inside a tick range. The contract reads a cumulative counter called secondsPerLiquidityInsideX128 from the Uniswap V3 pool and subtracts the value that was stored at the moment the position was staked. In Solidity 0.8 this subtraction is checked; if the stored initial value is larger than the current value the operation underflows, producing a huge uint256 number. The subsequent multiplication with the position’s liquidity then overflows, causing the internal function computeBoostedSecondsInsideX128 to revert. Because the public unstake function calls this internal routine, the revert propagates and the _unstake call fails, leaving the LP token permanently locked in the staking contract. The root cause is that the original Uniswap reference implementation was written for Solidity 0.7 where arithmetic overflow silently wrapped, while Maia’s version uses Solidity 0.8 where the same code throws. The bug can be triggered when a tick is initialized after the pool’s secondsPerLiquidityCumulativeX128 counter has approached its maximum value, so that the initial snapshot is near 2**256‑1 and the later snapshot is a small positive number. An attacker or any user who stakes a position that spans such a tick can later attempt to unstake and experience a transaction revert, effectively freezing their liquidity and any accrued rewards. The impact is a denial‑of‑service on the user’s funds: the UI will report “unstake failed” or simply show no change, while the user’s balance of the staked LP token remains unchanged and rewards are not paid. This issue affects any liquidity provider who uses the UniswapV3Staker contract, and it undermines confidence in the protocol because funds can become irretrievable without a contract upgrade. The problem was discovered during a formal security audit that highlighted the unsafe subtraction and the change in Solidity version semantics. It is hard to notice because the overflow only occurs after an extreme counter value that is unlikely in normal operation, and the code mirrors the official Uniswap library where the same pattern is considered safe. The appropriate mitigation is to perform the subtraction and multiplication in an unchecked block, or to add explicit checks that prevent the underflow, thereby restoring the original wrap‑around behaviour or avoiding the calculation when the counter would overflow. In abstract terms, this is a classic unchecked arithmetic bug that leads to a lock‑up denial‑of‑service condition in a DeFi staking contract.
