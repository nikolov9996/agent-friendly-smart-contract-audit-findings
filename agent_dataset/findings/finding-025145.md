---
id: 25145
severity: "Crit/High"
---

# WSTETHPriceFeed returns USD price Instead of EUR on oracle failure

## Description



## Proof of Concept

## Vulnerability Detail

The `WSTETHPriceFeed` has a fallback mechanism when the stETH-USD oracle fails. It calls `_shutDownAndSwitchToETHUSDxCanonical()` which calculates the price using ETH-USD and the canonical wstETH rate. However, the `_fetchPriceETHUSDxCanonical()` function in `CompositePriceFeed` never converts the USD price to EUR before returning.

This means after the stETH-USD oracle failure:

1. All prices returned are in USD (~1.05x higher than EUR)
2. The `lastGoodPrice` gets corrupted with a USD value
3. All subsequent operations use the wrong price denomination

## Impact

After stETH-USD oracle failure, all wstETH collateral operations will use incorrect prices. Users could be incorrectly liquidated or be able to borrow too much. The corrupted `lastGoodPrice` persists even after further fallbacks.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/WSTETHPriceFeed.sol#L70-L72](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/WSTETHPriceFeed.sol#L70-L72>)

```solidity
// If the STETH-USD feed is down, shut down and try to substitute it with the ETH-USD price
if (stEthUsdOracleDown) {
    return (_shutDownAndSwitchToETHUSDxCanonical(address(stEthUsdOracle.aggregator), ethUsdPrice), true);
}
```

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/CompositePriceFeed.sol#L76-L95](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/CompositePriceFeed.sol#L76-L95>)

```solidity
function _fetchPriceETHUSDxCanonical(uint256 _ethUsdPrice) internal returns (uint256) {
    assert(priceSource == PriceSource.ETHUSDxCanonical);
    (uint256 lstRate, bool exchangeRateIsDown) = _getCanonicalRate();

    if (exchangeRateIsDown) {
        priceSource = PriceSource.lastGoodPrice;
        return lastGoodPrice;
    }

    // Calculate the canonical LST-USD price: USD_per_LST = USD_per_ETH * underlying_per_LST
    uint256 lstUsdCanonicalPrice = _ethUsdPrice * lstRate / 1e18;  // @audit - USD, not EUR!

    uint256 bestPrice = LiquityMath._min(lstUsdCanonicalPrice, lastGoodPrice);

    lastGoodPrice = bestPrice;  // @audit - corrupts lastGoodPrice with USD value

    return bestPrice;  // @audit - returns USD instead of EUR
}
```

## Recommendation

Convert the USD price to EUR in the `_fetchPriceETHUSDxCanonical()` function or override it in `WSTETHPriceFeed` to include EUR conversion:

```solidity
function _fetchPriceETHUSDxCanonical(uint256 _ethUsdPrice) internal override returns (uint256) {
    (uint256 lstRate, bool exchangeRateIsDown) = _getCanonicalRate();
    (uint256 eurUsdPrice, bool eurUsdOracleDown) = _getOracleAnswer(eurUsdOracle);

    if (exchangeRateIsDown || eurUsdOracleDown) {
        priceSource = PriceSource.lastGoodPrice;
        return lastGoodPrice;
    }

    uint256 lstUsdCanonicalPrice = _ethUsdPrice * lstRate / 1e18;
    uint256 lstEurCanonicalPrice = FixedPointMathLib.divWad(lstUsdCanonicalPrice, eurUsdPrice);

    uint256 bestPrice = LiquityMath._min(lstEurCanonicalPrice, lastGoodPrice);
    lastGoodPrice = bestPrice;

    return bestPrice;
}
```
