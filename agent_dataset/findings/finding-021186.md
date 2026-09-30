---
id: 21186
severity: "High"
---

# Value of asset token can be incorrect when usage of ETH/USD Chainlink oracle is needed

## Description

There are tokens that have token/ETH but no token/USD Chainlink oracles currently in which these tokens have the in scope token behaviors described in <https://code4rena.com/audits/2024-04-noya> and should be supported by this protocol. To support these tokens, the ETH/USD Chainlink oracle can be used as a part of the route set by the following `NoyaValueOracle.updatePriceRoute` function for converting the token amount to ETH first and then converting the converted ETH amount to USD.

```solidity
function updatePriceRoute(address asset, address base, address[] calldata s) external onlyMaintainer {
    priceRoutes[asset][base] = s;
    emit UpdatedPriceRoute(asset, base, s);
}
```

When converting the value of such token in ETH to USD, the following `ChainlinkOracleConnector.getValue` function would return `getValueFromChainlinkFeed(AggregatorV3Interface(primarySource), amount, getTokenDecimals(decimalsSource), isPrimaryInverse)`; because `amountIn` is in ETH’s decimals that is 18 and `uintprice` and `sourceTokenUnit` are in USD’s decimals that is 8 in the `getValueFromChainlinkFeed` function below, the value returned by the `ChainlinkOracleConnector.getValue` function is in ETH’s decimals. Hence, when converting such token amount to ETH first and then to USD, the value of the corresponding token amount is in ETH’s decimals instead of USD’s decimals. In comparison, if the token/USD oracle could exist and be used for such token, the value of such token returned by `ChainlinkOracleConnector.getValue` function would be in USD’s decimals instead of ETH’s decimals. Thus, the value of such token is much higher when using the token/ETH and ETH/USD oracles indirectly comparing to using the token/USD oracle directly given if such token/USD oracle can become existent in the future. If such token/USD oracle does become existent and be used in the `ChainlinkOracleConnector` contract in the future, the value of such token amount calculated previously using the token/ETH and ETH/USD oracles indirectly would be incorrectly much higher than the value of the same token amount newly calculated using the token/USD oracle directly.

```solidity
function getValue(address asset, address baseToken, uint256 amount) public view returns (uint256) {
    if (asset == baseToken) {
        return amount;
    }

    (address primarySource, bool isPrimaryInverse) = getSourceOfAsset(asset, baseToken);
    if (primarySource == address(0)) {
        revert NoyaChainlinkOracle_PRICE_ORACLE_UNAVAILABLE(asset, baseToken, primarySource);
    }
    address decimalsSource = isPrimaryInverse ? baseToken : asset;
    decimalsSource = decimalsSource == ETH || decimalsSource == USD ? primarySource : decimalsSource;
    return getValueFromChainlinkFeed(
        AggregatorV3Interface(primarySource), amount, getTokenDecimals(decimalsSource), isPrimaryInverse
    );
}

function getTokenDecimals(address token) public view returns (uint256) {
    uint256 decimals = IERC20Metadata(token).decimals();
    return 10 ** decimals;
}

function getValueFromChainlinkFeed(
    AggregatorV3Interface source,
    uint256 amountIn,
    uint256 sourceTokenUnit,
    bool isInverse
) public view returns (uint256) {
    int256 price;
    uint256 updatedAt;
    (, price,, updatedAt,) = source.latestRoundData();
    uint256 uintprice = uint256(price);
    if (block.timestamp - updatedAt > chainlinkPriceAgeThreshold) {
        revert NoyaChainlinkOracle_DATA_OUT_OF_DATE();
    }
    if (price <= 0) {
        revert NoyaChainlinkOracle_PRICE_ORACLE_UNAVAILABLE(address(source), address(0), address(0));
    }
    if (isInverse) {
        return (amountIn * sourceTokenUnit) / uintprice;
    }
    return (amountIn * uintprice) / (sourceTokenUnit);
}
```

## Proof of Concept

Please add the following test in `testFoundry\testOracle.sol`. This test will pass to demonstrate the described scenario.
    
```solidity
function test_assetTokenValueIsIncorrectWhenETHUSDChainlinkOracleIsNeeded() public {
    // Some tokens do not have token/USD oracle so token/ETH and ETH/USD oracles need to be used.
    // Following code compares method using token/ETH and ETH/USD oracles indirectly to method using token/USD oracle directly.

    address ETH_USD_FEED = 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419;

    vm.startPrank(owner);

    addTokenToChainlinkOracle(address(USDC), address(840), address(USDC_USD_FEED));
    addTokenToChainlinkOracle(address(USDC), address(0), address(USDC_ETH_FEED));
    addTokenToChainlinkOracle(address(0), address(840), address(ETH_USD_FEED));

    addTokenToNoyaOracle(address(USDC), address(chainlinkOracle));
    addTokenToNoyaOracle(address(0), address(chainlinkOracle));
    addTokenToNoyaOracle(address(840), address(chainlinkOracle));

    uint256 valueDirect = noyaOracle.getValue(address(USDC), address(840), 1e6);

    // when using USDC/USD oracle directly, 1e6 wei USDC is equivalent to 99998495 wei USD, which is in USD's decimals that is 8
    assertEq(valueDirect, 99998495);

    address[] memory assets = new address[](1);
    assets[0] = address(0);
    noyaOracle.updatePriceRoute(address(USDC), address(840), assets);

    uint256 valueIndirect = noyaOracle.getValue(address(USDC), address(840), 1e6);

    // when using USDC/ETH and ETH/USD oracles indirectly, 1e6 wei USDC is equivalent to 998152930103816659 wei USD, which is in ETH's decimals that is 18
    assertEq(valueIndirect, 998152930103816659);

    // value of 1e6 wei USDC is incorrectly much higher when using USDC/ETH and ETH/USD oracles indirectly comparing to using USDC/USD oracle directly
    assertEq(valueIndirect / valueDirect, 9981679525);

    vm.stopPrank();
}
```

## Recommendation

`getValueFromChainlinkFeed(AggregatorV3Interface(primarySource), amount, getTokenDecimals(decimalsSource), isPrimaryInverse)` returned by the `ChainlinkOracleConnector.getValue` function can be further divided by `10 ** 10` when `asset` is ETH, `baseToken` is USD, and `isPrimaryInverse` is false. This makes such return value be in USD’s decimals that is 8.

I think I see the problem, when decimalsSource is ETH/USD it treats the decimal as source.decimal() because they are not real ERC20. It is usually fine because ETH oracles are 18 decimals and USD oracles are 8 decimals which is same as the expected value. However, when ETH/USD oracle is used the logic would always consider it as 8 decimal (because ETH/USD oracle as 8 decimal) but in fact it should be treated as 18 decimal if we want the ETH decimal, hence the result is off by 10 decimals.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect valuation of assets that rely on an indirect price route using a token/ETH Chainlink feed followed by the ETH/USD feed. The root cause is a mismatch in decimal handling inside the ChainlinkOracleConnector.getValue function: when the amount is expressed in ETH’s 18‑decimal precision but the source token unit is derived from the ETH/USD feed, which reports prices with 8 decimals, the getValueFromChainlinkFeed routine returns a result still scaled to 18 decimals. Consequently the returned USD value is inflated by a factor of 10^10 compared to the expected 8‑decimal USD representation. This mis‑scaling can be exploited whenever a token does not have a direct token/USD oracle and the protocol falls back to the token/ETH + ETH/USD route. An attacker can supply such a token, cause the protocol to believe the token is worth far more USD, and thereby borrow excessive amounts, avoid liquidation, or manipulate collateral calculations. The impact is that users see wildly overstated USD balances, the protocol’s accounting assumptions are broken, and financial loss may occur through improper liquidations or over‑collateralisation. The condition occurs only for assets lacking a direct USD feed and only when the price route is configured to use the ETH/USD oracle as an intermediate step. Affected parties include token holders, lenders, borrowers, and the overall protocol that relies on accurate price feeds for risk management. The issue was discovered during a Code4rena audit when a test compared the direct USDC/USD price with the indirect USDC/ETH + ETH/USD price and observed a ten‑order‑of‑magnitude discrepancy. The bug is subtle because the returned numbers are still numerically plausible and the decimal mismatch is not obvious from the contract code, making it easy to miss in manual reviews. The correct fix is to normalize the result of getValueFromChainlinkFeed for the ETH/USD path, for example by dividing the output by 10**10 or by treating the ETH/USD feed as having 18 decimals, so that the final value is expressed in USD’s 8‑decimal format as the protocol expects. This adjustment restores the intended accounting model, ensures that users receive the correct USD valuation, and prevents over‑valuation attacks.
