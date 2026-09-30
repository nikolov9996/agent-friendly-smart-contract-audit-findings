---
id: 19171
severity: "High"
---

# When price is within position’s range, `deposit` at TokenisableRange can cause loss of funds

## Description

When slot0 price is within the range of tokenized position, function `deposit` needs to be called with both parameters, `n0` and `n1`, greater than zero. However, if price moves outside the range during the transaction, user will be charged an excessive fee.

## Proof of Concept

```solidity
if ( fee0+fee1 > 0 && ( n0 > 0 || fee0 == 0) && ( n1 > 0 || fee1 == 0 ) ){
    address pool = V3_FACTORY.getPool(address(TOKEN0.token), address(TOKEN1.token), feeTier * 100);
    (uint160 sqrtPriceX96,,,,,,)  = IUniswapV3Pool(pool).slot0();
    (uint256 token0Amount, uint256 token1Amount) = LiquidityAmounts.getAmountsForLiquidity( sqrtPriceX96, TickMath.getSqrtRatioAtTick(lowerTick), TickMath.getSqrtRatioAtTick(upperTick), liquidity);
    if (token0Amount + fee0 > 0) newFee0 = n0 * fee0 / (token0Amount + fee0);
    if (token1Amount + fee1 > 0) newFee1 = n1 * fee1 / (token1Amount + fee1);
    fee0 += newFee0;
    fee1 += newFee1; 
    n0   -= newFee0;
    n1   -= newFee1;
}
```

Suppose range is [120, 122] and current price is 121. Alice calls `deposit` with `{n0: 100, n1:100}`, if Price moves to 119 during execution (due to market fluctuations or malicious frontrunning), `getAmountsForLiquidity` will return 0 for `token1Amount`. As a result, `newFee1` will be equal to `n1`, which means all the 100 token1 will be charged as fee.

```solidity
(uint128 newLiquidity, uint256 added0, uint256 added1) = POS_MGR.increaseLiquidity(
    INonfungiblePositionManager.IncreaseLiquidityParams({
        tokenId: tokenId,
        amount0Desired: n0,
        amount1Desired: n1,
        amount0Min: n0 * 95 / 100,
        amount1Min: n1 * 95 / 100,
        deadline: block.timestamp
    })
);
```

Then, `increaseLiquidity` will succeed since `amount1Min` is now zero.

## Recommendation

Don’t use this to calculate fee:

```solidity
if ( fee0+fee1 > 0 && ( n0 > 0 || fee0 == 0) && ( n1 > 0 || fee1 == 0 ) ){
    address pool = V3_FACTORY.getPool(address(TOKEN0.token), address(TOKEN1.token), feeTier * 100);
    (uint160 sqrtPriceX96,,,,,,)  = IUniswapV3Pool(pool).slot0();
    (uint256 token0Amount, uint256 token1Amount) = LiquidityAmounts.getAmountsForLiquidity( sqrtPriceX96, TickMath.getSqrtRatioAtTick(lowerTick), TickMath.getSqrtRatioAtTick(upperTick), liquidity);
    if (token0Amount + fee0 > 0) newFee0 = n0 * fee0 / (token0Amount + fee0);
    if (token1Amount + fee1 > 0) newFee1 = n1 * fee1 / (token1Amount + fee1);
    fee0 += newFee0;
    fee1 += newFee1; 
    n0   -= newFee0;
    n1   -= newFee1;
}
```

Always use this:

```solidity
uint256 TOKEN0_PRICE = ORACLE.getAssetPrice(address(TOKEN0.token));
uint256 TOKEN1_PRICE = ORACLE.getAssetPrice(address(TOKEN1.token));
require (TOKEN0_PRICE > 0 && TOKEN1_PRICE > 0, "Invalid Oracle Price");
// Calculate the equivalent liquidity amount of the non-yet compounded fees
// Assume linearity for liquidity in same tick range; calculate feeLiquidity equivalent and consider it part of base liquidity 
feeLiquidity = newLiquidity * ( (fee0 * TOKEN0_PRICE / 10 ** TOKEN0.decimals) + (fee1 * TOKEN1_PRICE / 10 ** TOKEN1.decimals) )   
                            / ( (added0   * TOKEN0_PRICE / 10 ** TOKEN0.decimals) + (added1   * TOKEN1_PRICE / 10 ** TOKEN1.decimals) ); 
```

Again this concurrency execution environment stuff. There is no price moving “during” execution.

Again this concurrency execution environment stuff. There is no price moving “during” execution.

Hi @Keref, I guess there could be some misunderstanding. Here I mean when price is 121, user will need to submit the tx with {n0: 100, n1:100}, and price could move to 119 when tx gets executed. (something similar to slippage)

Hi, sorry I misunderstood the report, accepted.

See [PR#4](https://github.com/GoodEntry-io/ge/pull/4)

Remove complex fee clawing strategy.  
PR: <https://github.com/GoodEntry-io/ge/pull/4>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the deposit routine of a tokenised Uniswap V3 range position. The function expects the caller to supply positive amounts for both tokens (n0 and n1) when the pool price is inside the position’s tick range. Inside the routine the contract reads the current pool price from slot0, calls LiquidityAmounts.getAmountsForLiquidity to compute the amount of each token that corresponds to the existing liquidity, and then scales the pending fees (fee0 and fee1) proportionally to the supplied amounts using the formula newFee0 = n0 * fee0 / (token0Amount + fee0) (and similarly for token1). This calculation assumes that token0Amount and token1Amount are both non‑zero. If, between the moment the transaction is signed and the moment it is executed, the pool price moves outside the position’s range, one of the token amounts returned by getAmountsForLiquidity becomes zero. When token1Amount is zero, the denominator of the second formula collapses to fee1, causing newFee1 to equal n1 – the entire amount the user intended to deposit is treated as a fee. The contract then deducts this fee from n1, leaving the user with no token1 deposited while still being charged the full amount. From the user’s perspective the transaction appears to succeed, but the expected token balance is missing or reduced to zero, effectively “funds disappear”. The issue is triggered only when price slippage or a front‑running trade pushes the price out of the tick range during execution, a condition that is not obvious during static analysis because the price is read from the pool at runtime. The bug was uncovered during a security audit that simulated price movement and observed the fee‑clawback logic misbehaving. It is hard to notice because under normal market conditions the price stays within the range and the fee calculation yields reasonable values. The root cause is the reliance on a volatile on‑chain price to compute fee proportions without safeguarding against zero token amounts, leading to a division‑by‑zero‑like situation and an excessive fee charge. To remediate, the contract should avoid using the pool’s instantaneous price for fee scaling; instead it should compute fees based on oracle‑derived stable prices or on the amounts the user actually supplied, and it must enforce that both token amounts are greater than zero before applying the proportional fee formula. Adding explicit checks that reject a deposit when either token amount returned by getAmountsForLiquidity is zero, or capping the fee to the supplied amount, eliminates the possibility of charging the full deposit as a fee and restores the intended accounting guarantees.
