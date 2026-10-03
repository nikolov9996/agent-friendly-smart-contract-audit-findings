---
id: 25681
severity: "Medium"
---

# Performing a direct multiplication in _getPriceFromSqrtX96 will overflow for some uniswap pools

## Description



## Proof of Concept

## Vulnerability Detail

The `LenderCommitmentGroup_Smart` uses the price obtained from the uniswap v3 pool in order to compute the amount of collateral that must be deposited in order to perform a borrow. Currently, the prices are fetched via the `_getUniswapV3TokenPairPrice` function:

```solidity
// LenderCommitmentGroup_Smart.sol
function _getUniswapV3TokenPairPrice(uint32 _twapInterval)
        internal
        view
        returns (uint256)
    {
        // represents the square root of the price of token1 in terms of token0

        uint160 sqrtPriceX96 = getSqrtTwapX96(_twapInterval);

        //this output is the price ratio expanded by 1e18
        return _getPriceFromSqrtX96(sqrtPriceX96);
    }
```

This function will perform two actions:

1. Get the `sqrtPriceX96` from the uniswap pool by querying the pool's TWAP or the pool's `slot0` function. It is important to note that the returned `sqrtPriceX96` is a `uint160` value that **can store numbers bigger than 128 bits:**

```solidity
    // LenderCommitmentGroup_Smart.sol

    function getSqrtTwapX96(uint32 twapInterval)
            public
            view
            returns (uint160 sqrtPriceX96)
        {
            if (twapInterval == 0) {
                // return the current price if twapInterval == 0
                (sqrtPriceX96, , , , , , ) = IUniswapV3Pool(UNISWAP_V3_POOL)
                    .slot0();
            } else {
                uint32[] memory secondsAgos = new uint32[](2);
                secondsAgos[0] = twapInterval; // from (before)
                secondsAgos[1] = 0; // to (now)

                (int56[] memory tickCumulatives, ) = IUniswapV3Pool(UNISWAP_V3_POOL)
                    .observe(secondsAgos);

                // tick(imprecise as it's an integer) to price
                sqrtPriceX96 = TickMath.getSqrtRatioAtTick(
                    int24(
                        (tickCumulatives[1] - tickCumulatives[0]) /
                            int32(twapInterval)
                    )
                );
            }
        }
```

2. After obtaining the `sqrtPriceX96` , the `priceX96` will be obtained by multiplying `sqrtPriceX96` by itself and dividing it by `(2**96)` :

```solidity
    // LenderCommitmentGroup_Smart.sol
    function _getPriceFromSqrtX96(uint160 _sqrtPriceX96)
            internal
            pure
            returns (uint256 price_)
        {

            uint256 priceX96 = (uint256(_sqrtPriceX96) * uint256(_sqrtPriceX96)) /
                (2**96);

            // sqrtPrice is in X96 format so we scale it down to get the price
            // Also note that this price is a relative price between the two tokens in the pool
            // It's not a USD price
            price_ = priceX96;
        }
```

The problem is that the `_getPriceFromSqrtX96` performs a direct multiplication between `_sqrtPriceX96` by itself. As mentioned in step 1, this multiplication can lead to overflow because the `_sqrtPriceX96` value returned by the Uniswap pool **can be a numer larger than 128 bits.**

As an example, take [Uniswap's WBTC/SHIBA pool](<https://etherscan.io/address/0x1153C8F2B05Fdde2dB507c8D16E49d4C7405c907#readContract>) and query `slot0`. At timestamp **1714392894,** the `slot0` value returned is 380146371870332863053439965317548561928, which is a 129 bit value. When the `_getPriceFromSqrtX96` gets executed for the WBTC/SHIBA pool, an overflow will always occur because a multiplication of two 129-bit integers surpasses 256 bits.

Note how this is also handled in [Uniswap's official Oracle Library](<https://github.com/Uniswap/v3-periphery/blob/main/contracts/libraries/OracleLibrary.sol#L58>)] contract, where a check is performed to ensure that no overflows can occur.

## Impact

Medium. Some uniswap pool's will be unusable and will DoS in LenderCommitmentGroup_Smart because the uniswap price computations will always overflow.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L559](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L559>)

## Recommendation

Use [Uniswap's Fullmath library](<https://github.com/Uniswap/v3-core/blob/main/contracts/libraries/FullMath.sol>) to perform the multiplication in `_getPriceFromSqrtX96`, which already handles this situation:

```diff
// LenderCommitmentGroup_Smart.sol
function _getPriceFromSqrtX96(uint160 _sqrtPriceX96)
        internal
        pure
        returns (uint256 price_)
    {

-        uint256 priceX96 = (uint256(_sqrtPriceX96) * uint256(_sqrtPriceX96)) /
-            (2**96);
+        uint256 priceX96 = FullMath.mulDiv(uint256(_sqrtPriceX96), uint256(_sqrtPriceX96), (2**96);

        // sqrtPrice is in X96 format so we scale it down to get the price
        // Also note that this price is a relative price between the two tokens in the pool
        // It's not a USD price
        price_ = priceX96;
    }
```
