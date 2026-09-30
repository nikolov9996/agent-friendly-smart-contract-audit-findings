---
id: 19173
severity: "High"
---

# Overflow can still happen when calculating `priceX8` inside `poolMatchesOracle` operation

## Description

`poolMatchesOracle` is used to compare price calculated from uniswap v3 pool and chainlink oracle and decide whether rebalance should happened or not. `priceX8` will be holding price information calculated using `sqrtPriceX96` and when operations is performed, it will try to scale down using `2 ** 12`. However, the scale down is not enough and overflow can still happened.

## Proof of Concept

Consider this scenario, The GeVault is using WBTC for `token0` and WETH for `token1`.

These are information for the WBTC/WETH from uniswap v3 pool (0x4585FE77225b41b697C938B018E2Ac67Ac5a20c0):

slot0 data (at current time) :
```solidity
sqrtPriceX96   uint160 :  31520141554881197083247204479961147
```
`token0` (WBTC) decimals is 8 and `token1` (WETH) decimals is 18.

Using these information, try to reproduce the `priceX8` calculation :
```solidity
function testOraclePrice() public {
    uint160 sqrtPriceX96 = 31520141554881197083247204479961147;
    // decimals0 is 8
    uint priceX8 = 10 ** 8;
    // Overflow if dont scale down the sqrtPrice before div 2*192 
    // @audit - the overflow still possible
    priceX8 =
        (priceX8 * uint(sqrtPriceX96 / 2 ** 12) ** 2 * 1e8) /
        2 ** 168;
    // decimals1 is 18
    priceX8 = priceX8 / 10 ** 18;
    assertEq(true, true);
}
```
the test result in overflow :
```
[FAIL. Reason: Arithmetic over/underflow] testOraclePrice() 
```
This will cause calculation still overflow, even using the widely used WBTC/WETH pair

## Recommendation

Consider to change the scale down using the recommended value from uniswap v3 library:

or change the scale down similar to the one used inside library
```solidity
function poolMatchesOracle() public view returns (bool matches){
    (uint160 sqrtPriceX96,,,,,,) = uniswapPool.slot0();
    
    uint decimals0 = token0.decimals();
    uint decimals1 = token1.decimals();
    uint priceX8 = 10**decimals0;
    // Overflow if dont scale down the sqrtPrice before div 2*192
    // @audit - the overflow still possible
    priceX8 = priceX8 * uint(sqrtPriceX96 / 2 ** 12) ** 2 * 1e8 / 2**168;
    priceX8 = priceX8 / 10**decimals1;
    uint oraclePrice = 1e8 * oracle.getAssetPrice(address(token0)) / oracle.getAssetPrice(address(token1));
    if (oraclePrice < priceX8 * 101 / 100 && oraclePrice > priceX8 * 99 / 100) matches = true;
}
```

See [PR#3](https://github.com/GoodEntry-io/ge/pull/3).

Scale down `sqrtPriceX96` to prevent overflow.  
PR: <https://github.com/GoodEntry-io/ge/pull/3>

## Derived Narrative

The following field is derived content and may not be source-grounded:

An overflow vulnerability exists in the price calculation performed by the poolMatchesOracle function of the GoodEntry vault. The function reads the sqrtPriceX96 value from a Uniswap V3 pool, scales it down by dividing by 2**12, squares the result and then multiplies by a factor derived from the token decimals to obtain a price expressed with 8 decimal places (priceX8). Because the scaling factor (2**12) is far smaller than the factor required to keep the intermediate product within the 256‑bit unsigned integer range, the multiplication and squaring can exceed the maximum uint256 value before the final division by 2**168 is applied. When the overflow occurs the arithmetic wraps or reverts, causing priceX8 to be incorrect or the whole transaction to fail. The bug is triggered when the pool contains assets with a large disparity in decimal places, such as WBTC (8 decimals) paired with WETH (18 decimals), and when the sqrtPriceX96 value is large, as demonstrated by the test case that reproduces an overflow with the real WBTC/WETH pool data. The overflow prevents the contract from correctly comparing the on‑chain price with the Chainlink oracle price, so the rebalance decision logic may never evaluate to true. As a result the vault can stay in an unbalanced state, exposing users to stale pricing, potential arbitrage loss, or even permanent loss of funds if the contract relies on periodic rebalancing to maintain collateral ratios. The issue was discovered during a Code4rena audit by inspecting the arithmetic expression and reproducing the failure with a unit test that triggered an arithmetic over/underflow exception. The problem is subtle because the overflow happens only for certain token pairs and does not manifest as an obvious error message; it simply causes the transaction to revert, which can be mistaken for a generic failure. The correct mitigation is to use the scaling factor recommended by the Uniswap V3 library (for example, FullMath.mulDiv with the library’s Q96 constant) or to apply a larger down‑scaling (such as dividing sqrtPriceX96 by 2**96 before squaring) so that the intermediate product stays within the uint256 range. By adopting the library’s price‑calculation routine or by explicitly matching the scaling used in the official Uniswap SDK, the overflow is eliminated and the price comparison works as intended, restoring the vault’s ability to rebalance safely.
