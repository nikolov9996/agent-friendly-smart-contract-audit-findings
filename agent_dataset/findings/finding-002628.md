---
id: 2628
severity: "High"
---

# Liquidity is incorrectly calcu- lated during addLiquidity() for V3AMO, causing DoS. Found by 0x37, pkqs90, s1ce, spark1

## Description

V3 has the same liquidity calculation as UniswapV3. Currently, when adding liquidity, the amount of liquidity that is suppose to add is calculated by liquidity=(usdAmount*currentLiquidity)/IERC20Upgradeable(usd).balanceOf(pool);. This is incorrect in the terms of UniswapV3, because there may be multiple tickLower/tickUpper positions covering the current tick. Also, since anyone can add a LP position to the pool, so attackers can easily DoS this function. Consider an attacker adds an unbalanced LP position that deposits a lot of Boost tokens but doesn't deposit USD tokens. This would increase the total liquidity, and inflate the amount of liquidity calculated in the above formula, which would lead to an increase of USD tokens required to mint the liquidity. When the amount of requried USD token is above the approved usdAmount, the liquidity minting would fail. See the following PoC section for a more detailed example.
```solidity
function _addLiquidity(
    uint256 usdAmount,
    uint256 minBoostSpend,
    uint256 minUsdSpend,
    uint256 deadline
) internal override returns (uint256 boostSpent, uint256 usdSpent, uint256 liquidity) {
    // Calculate the amount of BOOST to mint based on the usdAmount and boostMultiplier
    uint256 boostAmount = (toBoostAmount(usdAmount) * boostMultiplier) / FACTOR;
    // Mint the specified amount of BOOST tokens to this contract's address
    IMinter(boostMinter).protocolMint(address(this), boostAmount);
    // Approve the transfer of BOOST and USD tokens to the pool
    IERC20Upgradeable(boost).approve(pool, boostAmount);
    IERC20Upgradeable(usd).approve(pool, usdAmount);
    (uint256 amount0Min, uint256 amount1Min) = sortAmounts(minBoostSpend, minUsdSpend);
    uint128 currentLiquidity = IV3Pool(pool).liquidity();
    liquidity = (usdAmount * currentLiquidity) / IERC20Upgradeable(usd).balanceOf(pool);
    // Add liquidity to the BOOST-USD pool within the specified tick range
    (uint256 amount0, uint256 amount1) = IV3Pool(pool).mint(
        address(this),
        tickLower,
        tickUpper,
        uint128(liquidity),
        amount0Min,
        amount1Min,
        deadline
    );
}
```
Internal pre-conditions N/A External pre-conditions N/A Attack Path Attackers can brick addLiquidity function by depositing LP. Attackers can deposit LP to make add liquidity fail, which also makes mintSellFarm() fail. This is an important feature to keep Boost/USD pegged, thus a high severity issue. This is basically no cost for attackers since the Boost/USD will always go back to 1:1 so no impermanent loss is incurred.

## Proof of Concept

Add the following code in V3AMO.test.ts. It does the following: 1. Add unbalanced liquidity so that total liquidity increases, but USD.balanceOf(pool) does not increase. 2. Mint some USD to V3AMO for adding liquidity. 3. Try to add liquidity, but it fails due to incorrect liquidity calculation (tries to add too much liquidity for not enough USD tokens).
```solidity
it("Should execute addLiquidity successfully", async function() {
    // Step 1: Add unbalanced liquidity so that total liquidity increases, but USD.balanceOf(pool) does not increase.
    console.log(await pool.slot0());
    await boost.connect(boostMinter).mint(admin.address, boostDesired * 100n);
    await testUSD.connect(boostMinter).mint(admin.address, usdDesired * 100n);
    await boost.approve(poolAddress, boostDesired * 100n);
    await testUSD.approve(poolAddress, usdDesired * 100n);
    console.log(await boost.balanceOf(admin.address));
    console.log(await testUSD.balanceOf(admin.address));
    await pool.mint(
        amoAddress,
        -276325 - 10,
        tickUpper,
        liquidity * 3n,
        0,
        0,
        deadline
    );
    console.log(await boost.balanceOf(admin.address));
    console.log(await testUSD.balanceOf(admin.address));
    // Step 2: Mint some USD to V3AMO for adding liquidity.
    await testUSD.connect(admin).mint(amoAddress, ethers.parseUnits("1000", 6));
    const usdBalance = await testUSD.balanceOf(amoAddress);
    // Step 3: Add liquidity fails due to incorrect liquidity calculation.
    await expect(V3AMO.connect(amo).addLiquidity(
        usdBalance,
        1,
        1,
        deadline
    )).to.emit(V3AMO, "AddLiquidity");
});
```

## Recommendation

Use the UniswapV3 library for calculating liquidity: https://github.com/Uniswap/v3-periphery/blob/main/contracts/libraries/LiquidityAmounts.sol#L56
```solidity
function getLiquidityForAmounts(
    uint160 sqrtRatioX96,
    uint160 sqrtRatioAX96,
    uint160 sqrtRatioBX96,
    uint256 amount0,
    uint256 amount1
) internal pure returns (uint128 liquidity) {
    if (sqrtRatioAX96 > sqrtRatioBX96) (sqrtRatioAX96, sqrtRatioBX96) = (sqrtRatioBX96, sqrtRatioAX96);
    if (sqrtRatioX96 <= sqrtRatioAX96) {
        liquidity = getLiquidityForAmount0(sqrtRatioAX96, sqrtRatioBX96, amount0);
    } else if (sqrtRatioX96 < sqrtRatioBX96) {
        uint128 liquidity0 = getLiquidityForAmount0(sqrtRatioX96, sqrtRatioBX96, amount0);
        uint128 liquidity1 = getLiquidityForAmount1(sqrtRatioAX96, sqrtRatioX96, amount1);
        liquidity = liquidity0 < liquidity1 ? liquidity0 : liquidity1;
    } else {
        liquidity = getLiquidityForAmount1(sqrtRatioAX96, sqrtRatioBX96, amount1);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

An incorrect liquidity calculation is performed in the addLiquidity function of the V3AMO contract. The code computes the amount of liquidity to mint as (usdAmount * currentLiquidity) / IERC20Upgradeable(usd).balanceOf(pool). This formula assumes that the pool’s total liquidity is represented by a single price range, which is true for a simple Uniswap V2 pool but not for Uniswap V3 where multiple tick ranges can overlap the current price. Because the contract does not take the tickLower/tickUpper bounds into account, the computed liquidity can be dramatically inflated when the pool already contains an unbalanced position that holds a large amount of the BOOST token but very little USD. An attacker can create such a position at no cost to the protocol, because the BOOST/USD pair is designed to stay at a 1:1 peg and therefore does not suffer impermanent loss. By depositing a heavily BOOST‑biased LP, the attacker raises the pool’s total liquidity while the USD balance of the pool remains unchanged. Subsequent calls to addLiquidity use the inflated pool.liquidity() value, causing the formula to demand more USD than the caller has approved. The mint operation then reverts, effectively denying any further liquidity addition. This denial‑of‑service condition also breaks the mintSellFarm workflow that relies on successful liquidity provision, so users attempting to add liquidity or sell farmed tokens see their transactions fail or receive no tokens, even though they supplied the correct amount of USD. The issue was discovered during a manual audit when the testers observed that a deliberately unbalanced LP caused addLiquidity to revert despite sufficient USD approval. The bug is subtle because the contract does not check that the USD balance of the pool matches the proportion of total liquidity, and the failure only appears when the pool already contains a skewed position. The proper fix is to replace the custom formula with the official Uniswap V3 LiquidityAmounts library, which calculates liquidity based on the current sqrt price, the lower and upper tick bounds, and the actual token amounts supplied. Using the library ensures that the required USD amount reflects the true price range and prevents an attacker from inflating the liquidity denominator. In summary, the vulnerability is a mis‑calculated liquidity amount that enables an attacker to DoS the addLiquidity function by adding an unbalanced LP, leading to failed transactions, loss of expected liquidity, and potential disruption of the protocol’s peg mechanism.
