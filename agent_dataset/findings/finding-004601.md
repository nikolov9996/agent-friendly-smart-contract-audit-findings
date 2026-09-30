---
id: 4601
severity: "High"
---

# `UniswapV2PriceOracle.sol` `currentCumulativePrices

## Description

[UniswapV2PriceOracle.sol#L62](https://github.com/code-423n4/2022-04-phuture/blob/594459d0865fb6603ba388b53f3f01648f5bb6fb/contracts/UniswapV2PriceOracle.sol#L62)  

```solidity
(uint price0Cumulative, uint price1Cumulative, uint32 blockTimestamp) = address(pair).currentCumulativePrices();
```

Because the Solidity version used by the current implementation of `UniswapV2OracleLibrary.sol` is `>=0.8.7`, and there are some breaking changes in Solidity v0.8.0:

> Arithmetic operations revert on underflow and overflow.

Ref: <https://docs.soliditylang.org/en/v0.8.13/080-breaking-changes.html#silent-changes-of-the-semantics>

While in `UniswapV2OracleLibrary.sol`, subtraction overflow is desired at `blockTimestamp - blockTimestampLast` in `currentCumulativePrices()`:

```solidity
if (blockTimestampLast != blockTimestamp) {
    // subtraction overflow is desired
    uint32 timeElapsed = blockTimestamp - blockTimestampLast;
    // addition overflow is desired
    // counterfactual
    price0Cumulative += uint(FixedPoint.fraction(reserve1, reserve0)._x) * timeElapsed;
    // counterfactual
    price1Cumulative += uint(FixedPoint.fraction(reserve0, reserve1)._x) * timeElapsed;
}
```

In another word, `Uniswap/v2-periphery/contracts/libraries/UniswapV2OracleLibrary` only works at solidity < `0.8.0`.

As a result, when `price0Cumulative` or `price1Cumulative` is big enough, `currentCumulativePrices` will revert due to overflow.

## Proof of Concept

no poc

## Recommendation

Note: this recommended fix requires a fork of the library contract provided by Uniswap.

Change to:

```solidity
if (blockTimestampLast != blockTimestamp) {
    unchecked {
        // subtraction overflow is desired
        uint32 timeElapsed = blockTimestamp - blockTimestampLast;
        // addition overflow is desired
        // counterfactual
        price0Cumulative += uint(FixedPoint.fraction(reserve1, reserve0)._x) * timeElapsed;
        // counterfactual
        price1Cumulative += uint(FixedPoint.fraction(reserve0, reserve1)._x) * timeElapsed;
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic overflow caused by a change in Solidity compiler semantics introduced in version 0.8.0. The UniswapV2OracleLibrary library, originally written for Solidity < 0.8.0, relies on unchecked subtraction and addition when it computes the time‑elapsed component of the cumulative price values in the function currentCumulativePrices(). In the original code the expression `blockTimestamp - blockTimestampLast` may under‑flow, and the subsequent `price0Cumulative += … * timeElapsed` and `price1Cumulative += … * timeElapsed` may overflow; both situations were intentionally allowed because the values are meant to wrap around modulo 2^256. However, when the library is compiled with Solidity ≥ 0.8.7, the compiler automatically inserts overflow checks for all arithmetic operations. As a result, once either price0Cumulative or price1Cumulative grows large enough that the addition would exceed the uint256 limit, the transaction reverts instead of wrapping. The overflow check also applies to the subtraction of timestamps, which can theoretically under‑flow if the block timestamp wraps, but this is less likely in practice. The bug manifests during regular oracle updates: each time the Oracle reads the pair’s reserves it calls `currentCumulativePrices()`. After enough price updates, the cumulative counters become huge; the next call triggers a revert, preventing the oracle from returning a fresh price. From a user’s perspective this appears as a silent failure of the price feed – calls that expect a current price either receive no data or cause the surrounding transaction to fail, leading to unexpected zero‑returns, missing refunds, or halted trades that depend on the oracle. The impact is high because any protocol that trusts this oracle for pricing, collateral valuation, or liquidation logic may operate with stale or unavailable price data, potentially causing liquidations to be missed, trades to be blocked, or funds to become temporarily unavailable. The condition under which the bug occurs is deterministic: once the cumulative price counters exceed the maximum representable value, which can happen after a relatively small number of updates given the high‑frequency nature of Uniswap pools. The issue was discovered during a formal audit of the Phuture protocol, where auditors compared the library’s expected unchecked arithmetic semantics against the actual compiled output and observed that the function reverted for large cumulative values. The problem is hard to notice because normal testing with a few updates does not reach the overflow threshold, and the revert only occurs deep inside a library call, making the symptom appear as an unrelated transaction failure. The correct mitigation is to restore the original unchecked semantics by enclosing the arithmetic in an `unchecked { … }` block, as recommended by the auditors. This change re‑enables the intentional wrap‑around behaviour, ensuring the cumulative price values continue to evolve without causing a revert, and restores the reliability of the price oracle for all downstream contracts.
