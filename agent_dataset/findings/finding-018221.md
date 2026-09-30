---
id: 18221
severity: "High"
---

# Reth `poolPrice` calculation may overflow

## Description

The Reth derivative contract implements the `poolPrice` function to get the spot price of the derivative asset using a Uniswap V3 pool. The function queries the pool to fetch the `sqrtPriceX96` and does the following calculation:

```solidity
function poolPrice() private view returns (uint256) {
    address rocketTokenRETHAddress = RocketStorageInterface(
        ROCKET_STORAGE_ADDRESS
    ).getAddress(
            keccak256(
                abi.encodePacked("contract.address", "rocketTokenRETH")
            )
        );
    IUniswapV3Factory factory = IUniswapV3Factory(UNI_V3_FACTORY);
    IUniswapV3Pool pool = IUniswapV3Pool(
        factory.getPool(rocketTokenRETHAddress, W_ETH_ADDRESS, 500)
    );
    (uint160 sqrtPriceX96, , , , , , ) = pool.slot0();
    return (sqrtPriceX96 * (uint(sqrtPriceX96)) * (1e18)) >> (96 * 2);
}
```

The main issue here is that the multiplications in the expression `sqrtPriceX96 * (uint(sqrtPriceX96)) * (1e18)` may eventually overflow. This case is taken into consideration by the implementation of the [OracleLibrary.getQuoteAtTick](https://docs.uniswap.org/contracts/v3/reference/periphery/libraries/OracleLibrary#getquoteattick) function which is part of the Uniswap V3 periphery set of contracts.

```solidity
function getQuoteAtTick(
    int24 tick,
    uint128 baseAmount,
    address baseToken,
    address quoteToken
) internal pure returns (uint256 quoteAmount) {
    uint160 sqrtRatioX96 = TickMath.getSqrtRatioAtTick(tick);

    // Calculate quoteAmount with better precision if it doesn't overflow when multiplied by itself
    if (sqrtRatioX96 <= type(uint128).max) {
        uint256 ratioX192 = uint256(sqrtRatioX96) * sqrtRatioX96;
        quoteAmount = baseToken < quoteToken
            ? FullMath.mulDiv(ratioX192, baseAmount, 1 << 192)
            : FullMath.mulDiv(1 << 192, baseAmount, ratioX192);
    } else {
        uint256 ratioX128 = FullMath.mulDiv(sqrtRatioX96, sqrtRatioX96, 1 << 64);
        quoteAmount = baseToken < quoteToken
            ? FullMath.mulDiv(ratioX128, baseAmount, 1 << 128)
            : FullMath.mulDiv(1 << 128, baseAmount, ratioX128);
    }
}
```

Note that this implementation guards against different numerical issues. In particular, the if in line 58 checks for a potential overflow of `sqrtRatioX96` and switches the implementation to avoid the issue.

## Proof of Concept

no poc

## Recommendation

The `poolPrice` function can delegate the calculation directly to the [OracleLibrary.getQuoteAtTick](https://docs.uniswap.org/contracts/v3/reference/periphery/libraries/OracleLibrary#getquoteattick) function of the `v3-periphery` package:

```solidity
function poolPrice() private view returns (uint256) {
    address rocketTokenRETHAddress = RocketStorageInterface(
        ROCKET_STORAGE_ADDRESS
    ).getAddress(
            keccak256(
                abi.encodePacked("contract.address", "rocketTokenRETH")
            )
        );
    IUniswapV3Factory factory = IUniswapV3Factory(UNI_V3_FACTORY);
    IUniswapV3Pool pool = IUniswapV3Pool(
        factory.getPool(rocketTokenRETHAddress, W_ETH_ADDRESS, 500)
    );
    (, int24 tick, , , , , ) = pool.slot0();
    return OracleLibrary.getQuoteAtTick(tick, 1e18, rocketTokenRETHAddress, W_ETH_ADDRESS);
}
```

Using Chainlink to get price instead of poolPrice.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the way the Reth derivative contract computes the spot price of the underlying asset by directly squaring the square‑root price returned from a Uniswap V3 pool. The function reads the 160‑bit sqrtPriceX96 value, casts it to a 256‑bit integer and then evaluates sqrtPriceX96 * sqrtPriceX96 * 1e18 before shifting the result. Because sqrtPriceX96 can be close to 2^160, squaring it yields a value that may require up to 320 bits of precision. Multiplying this intermediate 320‑bit number by 1e18 therefore exceeds the 256‑bit capacity of Solidity’s uint256 type, causing a silent overflow. The overflow truncates the high‑order bits, producing a price that is dramatically lower or higher than the true market price. This mis‑calculation can be triggered whenever the pool price moves into a range where sqrtPriceX96 is larger than roughly 2^128, a situation that can arise under normal market volatility or when large trades push the price. An attacker who can influence the pool price can therefore cause the contract to report an incorrect spot price, leading to downstream functions that rely on poolPrice – such as minting, redemption or collateral valuation – to accept or dispense funds at a distorted rate. From a user’s perspective the symptoms may appear as a displayed price that is unexpectedly zero or far from market expectations, trades that return far fewer tokens than anticipated, or balances that seem to disappear after a transaction. The issue was discovered during a Code4rena audit when the reviewer examined the poolPrice implementation and noticed the unchecked multiplication. It is hard to notice because the overflow does not revert; the contract simply returns a wrapped value, and the UI may still show a numeric result, masking the underlying arithmetic error. The proper remediation is to avoid the naïve multiplication and instead delegate the price computation to Uniswap V3’s OracleLibrary.getQuoteAtTick, which uses FullMath to perform the calculation with overflow protection, or to replace the logic with a trusted oracle such as Chainlink. By using a library that conditionally scales the intermediate result or by employing safe‑math primitives, the contract can guarantee that the spot price reflects the true market value, preserving accounting integrity and preventing users from receiving incorrect amounts or losing funds.
