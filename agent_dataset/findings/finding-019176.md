---
id: 19176
severity: "High"
---

# Incorrect Solidity version in FullMath.sol can cause permanent freezing of assets for arithmetic underflow-induced revert

## Description

`TokenisableRange` makes use of the `LiquidityAmounts.getAmountsForLiquidity` helper function in its [`returnExpectedBalanceWithoutFees`](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L338), [`getTokenAmountsExcludingFees`](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L371C31-L371C31) and [`deposit`](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L240C18-L240C18) functions to convert UniswapV3 pool liquidity into estimated underlying token amounts.

This function `getAmountsForLiquidity` will trigger an arithmetic underflow whenever `sqrtRatioX96` is smaller than `sqrtRatioAX96`, causing these functions to revert until this ratio comes back in range and the math no longer overflows.

Such oracle price conditions are not only possible but also likely to happen in real market conditions, and they can be permanent (i.e. one asset permanently appreciating over the other one).

Moving up the stack, assuming that `LiquidityAmounts.getAmountsForLiquidity` can revert (which is shown in the below PoC with real-world conditions), both the [`returnExpectedBalanceWithoutFees`](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L338) and [`getTokenAmountsExcludingFees`](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L371C31-L371C31) functions can revert. In particular, the former [is called by the `claimFee()`](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L187) function, which is always called when [depositing](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L227) and [withdrawing](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/TokenisableRange.sol#L293) liquidity.

The root cause of this issue is that the FullMath.sol library, [imported from UniswapV3](https://github.com/Uniswap/v3-core/blob/main/contracts/libraries/FullMath.sol) was [altered to build with solidity v0.8.x](https://github.com/code-423n4/2023-08-goodentry/blob/71c0c0eca8af957202ccdbf5ce2f2a514ffe2e24/contracts/lib/FullMath.sol#L2), which has under/overflow protection; the library, however, makes use of these by design, so it won’t work properly when compiled in v0.8.0 or later:
```solidity
/// @dev Handles "phantom overflow" i.e., allows multiplication and division where an intermediate value overflows 256 bits
library FullMath {
```
When the fair exchange price of the pool backing the TokenisableRange’s falls outside the range (higher side), the `deposit` and `withdraw` will always revert, locking the underlying assets in the pool until the price swings to a different value that does not trigger an under/overflow. If the oracle price stays within this range indefinitely, the funds are permanently locked.

## Proof of Concept

I’ll prove that permanent freezing can happen in two steps:

* first I’ll show one condition where the underflow happens
* then, I’ll set up a fuzz test to prove that given an A and B ticker, we cannot find a market price lower than A such that the underflow does not happen

The most simple way to prove the first point is by calling `LiquidityAmounts.getAmountsForLiquidity` in isolation with real-world values:
```solidity
function testGetAmountsForLiquidityRevert() public {
    // real-world value: it's in fact the value returned by
    // V3_FACTORY.getPool(USDC, WETH, 500).slot0();
    // at block 17811921; it is around 1870 USDC per WETH
    uint160 sqrtRatioX96 = 1834502451234584391374419429242405;

    // start price and end corresponding to 1700 to 1800 USDC per WETH
    uint160 sqrtRatioAX96 = 1866972058592130739290643700340936;
    uint160 sqrtRatioBX96 = 1921904167735311150677430952623492;

    vm.expectRevert();
    LiquidityAmounts.getAmountsForLiquidity(sqrtRatioX96, sqrtRatioAX96, sqrtRatioBX96, 1e18);
}
```
However, a more integrated test that involves PositionManager can also be considered:
```solidity
function testPocReturnExpectedBalanceUnderflow() public {
    vm.createSelectFork(
        "mainnet",
        17811921
    );
    vm.startPrank(tokenWhale);
    TokenisableRange tr = new TokenisableRange();
    tr.initProxy(AaveOracle, USDC, WETH, 1700e10, 1800e10, "Test1", "T1", false);
    USDC.approve(address(tr), 100_000e6);
    tr.init(100_000e6, 0);
    vm.expectRevert();
    tr.returnExpectedBalance(0, 0);
}
```
Then, we can prove the second point with a negative fuzz test:
```solidity
function testFailPermanentFreeze(uint160 sqrtRatioX96) public {
    // start & and price, corresponding to 1700 to 1800 USDC per WETH
    uint160 sqrtRatioAX96 = 1866972058592130739290643700340936;
    uint160 sqrtRatioBX96 = 1921904167735311150677430952623492;

    // make sure that the market ratio is lower than the lower ticker
    // that is the range where I first observed the underflow
    // (WETH above 1800 USDC)
    sqrtRatioX96 = sqrtRatioX96 % (sqrtRatioAX96 - 1);

    // expect a revert here
    LiquidityAmounts.getAmountsForLiquidity(sqrtRatioX96, sqrtRatioAX96, sqrtRatioBX96, 1e18);
}
```

## Recommendation

Restore [the original FullMath.sol library](https://github.com/Uniswap/v3-core/blob/main/contracts/libraries/FullMath.sol) so it compiles with solc versions earlier than 0.8.0.
```solidity
// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.4.0 <0.8.0;

/// @title Contains 512-bit math functions
/// @notice Facilitates multiplication and division that can have overflow of an intermediate value without any loss of precision
/// @dev Handles "phantom overflow" i.e., allows multiplication and division where an intermediate value overflows 256 bits
```
Another possible option, which is however not recommended, is to enclose the non-assembly statements of FullMath.sol in an `unchecked` block.

There’s an error with those lib versions, and we will replace with libs from the [0.8 branch](https://github.com/Uniswap/v3-core/tree/main/contracts/libraries).

Use correct Uniswap for sol `^0.8` libs.  
PR: <https://github.com/GoodEntry-io/ge/commit/8b0feaec0005937c8e6c7ef9bf039a0c2498529a>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an arithmetic underflow caused by compiling the Uniswap V3 FullMath library with Solidity version 0.8.x, which introduces automatic overflow and underflow checks. FullMath is designed to perform 512‑bit multiplication and division using unchecked arithmetic; when compiled with Solidity 0.8 or later the built‑in checks trigger a revert whenever an intermediate value would overflow. In the TokenisableRange contract the helper function LiquidityAmounts.getAmountsForLiquidity is called to convert pool liquidity into token amounts. If the current sqrt price (sqrtRatioX96) is lower than the lower bound of the configured price range (sqrtRatioAX96), the calculation underflows and the function reverts. This revert propagates to higher‑level functions such as returnExpectedBalanceWithoutFees, getTokenAmountsExcludingFees, claimFee, deposit and withdraw. Because deposit and withdraw invoke claimFee on every operation, a price that stays outside the range makes every deposit or withdrawal transaction revert, effectively locking the underlying assets in the contract until the market price moves back into the range. In real markets the price can remain permanently on one side of the range, so the assets may be frozen forever. From a user’s point of view a deposit or withdrawal simply fails with a revert, the UI shows no change in balance, and the user may see their tokens appear to disappear or become inaccessible. The issue was discovered during a security audit that included a proof‑of‑concept test using real‑world Uniswap V3 slot0 data, which demonstrated that the underflow occurs with actual market prices. The bug is hard to notice because it only manifests under specific price conditions and the revert message does not reveal the underlying arithmetic problem. The proper fix is to restore the original FullMath implementation that is compiled with a Solidity compiler version earlier than 0.8.0, or alternatively wrap the arithmetic in an unchecked block, although the latter is not recommended. By using the correct library the phantom overflow behavior is restored, the underflow no longer triggers a revert, and deposits and withdrawals work as intended regardless of price movements, preserving the protocol’s accounting guarantees and preventing permanent asset lockup.
