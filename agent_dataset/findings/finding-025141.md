---
id: 25141
severity: "Low/Info"
---

# SDAIPriceFeed missing constructor price feed check

## Description



## Proof of Concept

## Vulnerability Detail

Unlike other price feeds (GNOPriceFeed, WBTCPriceFeed, etc.), `SDAIPriceFeed` does not call `_fetchPricePrimary()` in its constructor. This means:

1. `lastGoodPrice` starts at 0
2. If the first `fetchPrice()` call encounters an oracle failure, `_shutDownAndSwitchToLastGoodPrice()` returns 0
3. A price of 0 could cause division by zero or allow infinite borrowing

## Impact

If oracles fail on the first price fetch after deployment, the system returns a price of 0.

## Code Snippet

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/SDAIPriceFeed.sol#L13-L21](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/SDAIPriceFeed.sol#L13-L21>)

```solidity
constructor(address _daiUsdOracleAddress, address _eurUsdOracleAddress, uint256 _daiUsdStalenessThreshold, uint256 _usdEurStalenessThreshold, address _borrowerOperationsAddress, address _sdaiAddress)
    MainnetPriceFeedBase(_daiUsdOracleAddress, _daiUsdStalenessThreshold, _borrowerOperationsAddress)
{
    eurUsdOracle.aggregator = AggregatorV3Interface(_eurUsdOracleAddress);
    eurUsdOracle.stalenessThreshold = _usdEurStalenessThreshold;
    eurUsdOracle.decimals = eurUsdOracle.aggregator.decimals();

    sdai = IERC4626(_sdaiAddress);

    // @audit - missing: _fetchPricePrimary();
    // @audit - missing: assert(priceSource == PriceSource.primary);
}
```

Compare to GNOPriceFeed: [https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/GNOPriceFeed.sol#L17-L18](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/GNOPriceFeed.sol#L17-L18>)

```solidity
_fetchPricePrimary();
assert(priceSource == PriceSource.primary);
```

## Recommendation

Add initialization in the constructor:

```solidity
constructor(...) MainnetPriceFeedBase(...) {
    eurUsdOracle.aggregator = AggregatorV3Interface(_eurUsdOracleAddress);
    eurUsdOracle.stalenessThreshold = _usdEurStalenessThreshold;
    eurUsdOracle.decimals = eurUsdOracle.aggregator.decimals();

    sdai = IERC4626(_sdaiAddress);

    _fetchPricePrimary();
    assert(priceSource == PriceSource.primary);
}
```
