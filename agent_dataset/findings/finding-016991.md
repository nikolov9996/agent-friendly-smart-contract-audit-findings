---
id: 16991
severity: "High"
---

# Wrong calculation in function `LBRouter._getAmountsIn` make user lose a lot of tokens when swap through JoePair

## Description

```solidity
function LBRouter._getAmountsIn(amountOut) is a helper function to return the amounts in with given `amountOut`. This function will check the pair of `_token` and `_tokenNext` is `JoePair` or `LBPair` using `_binStep`.

  * If `_binStep == 0`, it will be a `JoePair` otherwise it will be an `LBPair`.

if (_binStep == 0) {
    (uint256 _reserveIn, uint256 _reserveOut, ) = IJoePair(_pair).getReserves();
    if (_token > _tokenPath[i]) {
        (_reserveIn, _reserveOut) = (_reserveOut, _reserveIn);
    }

    uint256 amountOut_ = amountsIn[i];
    // Legacy uniswap way of rounding
    amountsIn[i - 1] = (_reserveIn * amountOut_ * 1_000) / (_reserveOut - amountOut_ * 997) + 1;
} else {
    (amountsIn[i - 1], ) = getSwapIn(ILBPair(_pair), amountsIn[i], ILBPair(_pair).tokenX() == _token);
}
```
As we can see when `_binStep == 0` and `_token < _tokenPath[i]` (in another word we swap through `JoePair` and pair’s`token0` is `_token` and `token1` is `_tokenPath[i]`), it will
  1. Get the reserve of pair (`reserveIn`, `reserveOut`)
  2. Calculate the `_amountIn` by using the formula
```solidity
amountsIn[i - 1] = (_reserveIn * amountOut_ * 1_000) / (_reserveOut - amountOut_ * 997) + 1
```
But unfortunately the denominator `_reserveOut - amountOut_ * 997` seem incorrect. It should be `(_reserveOut - amountOut_) * 997`.  
We will do some math calculations here to prove the expression above is wrong.

**Input:**
  * `_reserveIn (rIn)`: reserve of `_token` in pair
  * `_reserveOut (rOut)`: reserve of `_tokenPath[i]` in pair
  * `amountOut_`: the amount of `_tokenPath` the user wants to gain

**Output:**
  * `rAmountIn`: the actual amount of `_token` we need to transfer to the pair.

**Generate Formula:**

Cause `JoePair` [takes 0.3%](https://help.traderjoexyz.com/en/welcome/faq-and-help/general-faq#what-are-trader-swap-joe-fees) of `amountIn` as fee, we get
  * `amountInDeductFee = amountIn' * 0.997`

Following the [constant product formula](https://docs.uniswap.org/protocol/V2/concepts/protocol-overview/glossary#constant-product-formula), we have
```solidity
        rIn * rOut = (rIn + amountInDeductFee) * (rOut - amountOut_)
    ==> rIn + amountInDeductFee = rIn * rOut / (rOut - amountOut_) + 1
    <=> amountInDeductFee = (rIn * rOut) / (rOut - amountOut_) - rIn + 1
    <=> rAmountIn * 0.997 = rIn * amountOut / (rOut - amountOut_) + 1
    <=> rAmountIn = (rIn * amountOut * 1000) / ((rOut - amountOut_) * 997) + 1
```
As we can see `rAmountIn` is different from `amountsIn[i - 1]`, the denominator of `rAmountIn` is `(rOut - amountOut_) * 997` when the denominator of `amountsIn[i - 1]` is `_reserveOut - amountOut_ * 997` (Missing one bracket)

## Proof of Concept

Here is our test script to describe the impacts
  * <https://gist.github.com/huuducst/6e34a7bdf37bb29f4b84d2faead94dc4>

You can place this file into `/test` folder and run it using
```bash
forge test --match-test testBugSwapJoeV1PairWithLBRouter --fork-url https://rpc.ankr.com/avalanche --fork-block-number 21437560 -vv
```
Explanation of test script: (For more detail you can read the comments from test script above)
  1. Firstly we get the Joe v1 pair WAVAX/USDC from JoeFactory.
  2. At the forked block, price `WAVAX/USDC` was around 15.57. We try to use LBRouter function `swapTokensForExactTokens` to swap `10$` WAVAX (10e18 wei) to `1$` USDC (1e6 wei). But it reverts with the error `LBRouter__MaxAmountInExceeded`. But when we swap directly to JoePair, it swap successfully `10$` AVAX (10e18 wei) to `155$` USDC (155e6 wei).
  3. We use LBRouter function `swapTokensForExactTokens` again with very large `amountInMax` to swap `1$` USDC (1e6 wei). It swaps successfully but needs to pay a very large amount WAVAX (much more than price).

## Recommendation

```solidity
if (_binStep == 0) {
    (uint256 _reserveIn, uint256 _reserveOut, ) = IJoePair(_pair).getReserves();
    if (_token > _tokenPath[i]) {
        (_reserveIn, _reserveOut) = (_reserveOut, _reserveIn);
    }

    uint256 amountOut_ = amountsIn[i];
    // Legacy uniswap way of rounding
    // Fix here 
    amountsIn[i - 1] = (_reserveIn * amountOut_ * 1_000) / ((_reserveOut - amountOut_) * 997) + 1;
} else {
    (amountsIn[i - 1], ) = getSwapIn(ILBPair(_pair), amountsIn[i], ILBPair(_pair).tokenX() == _token);
}
```

The warden has shown how, due to an incorrect order of operation, the math for the router will be incorrect.

While the error could be considered a typo, the router is the designated proper way of performing a swap, and due to this finding, the math will be off.

Because the impact shows an incorrect logic, and a broken invariant (the router uses incorrect amounts, sometimes reverting, sometimes costing the end user more tokens than necessary), I believe High Severity to be appropriate.

Mitigation will require refactoring and may be aided by the test case offered in this report.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the router’s helper function that computes the input amount required for a given output amount when swapping through a legacy JoePair (i.e., when the bin step is zero). The function uses the formula `(_reserveIn * amountOut_ * 1_000) / (_reserveOut - amountOut_ * 997) + 1` to derive the amount of the input token that must be sent to the pair. Because of missing parentheses, the denominator is evaluated as `_reserveOut - (amountOut_ * 997)` instead of the mathematically correct `(_reserveOut - amountOut_) * 997`. This precedence error causes the router to underestimate the necessary input amount or, in some cases, to compute a value that is dramatically larger than the true amount. The root cause is a simple operator‑ordering typo that changes the constant‑product invariant used by the Uniswap‑style AMM. An attacker does not need to manipulate the contract; the bug is triggered simply by any user who invokes `swapTokensForExactTokens` (or similar) through the LBRouter while the path includes a JoePair where the token being swapped in is token0 of the pair. Under these conditions the router will either revert with a "MaxAmountInExceeded" error or will accept the transaction but charge the user a far higher amount of the input token than market rates dictate. From the user’s perspective the symptoms are a failed swap or a successful swap that unexpectedly drains an excessive amount of tokens, often leaving the user’s balance lower than expected or even zero for the swapped token. The impact is loss of funds and degraded user experience, and the bug can also break higher‑level protocol logic that assumes the router returns correct amounts. The issue was discovered during a formal audit by reproducing a swap on a forked Avalanche block, observing a revert, and then confirming the mismatch by comparing the router’s calculation against the standard constant‑product formula. The problem is subtle because the arithmetic error does not produce an obvious overflow or revert; it merely skews the price calculation, which can be mistaken for normal slippage. To remediate the issue the denominator must be rewritten with the proper grouping: `(_reserveOut - amountOut_) * 997`. This restores the correct application of the 0.3% fee factor and respects the invariant `reserveIn * reserveOut = (reserveIn + amountInAfterFee) * (reserveOut - amountOut)`. After the fix, the router will compute accurate input amounts, preventing unnecessary token loss and ensuring swaps behave as users expect.
