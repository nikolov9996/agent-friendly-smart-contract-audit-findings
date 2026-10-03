---
id: 25139
severity: "Medium"
---

# API3 oracle future timestamp causes temporary DoS via underflow

## Description



## Proof of Concept

## Vulnerability Detail

The API3 DataFeedServer allows timestamps to be up to 1 hour in the future:

```solidity
// From API3 DataFeedServer.sol
require(
    timestamp < block.timestamp + 1 hours,
    "Timestamp not valid"
);
```

However, `MainnetPriceFeedBase._isValidChainlinkPrice()` is as follows:

```solidity
return chainlinkResponse.success && block.timestamp - chainlinkResponse.timestamp < _stalenessThreshold
    && chainlinkResponse.answer > 0;
```

When `chainlinkResponse.timestamp > block.timestamp`, the subtraction `block.timestamp - chainlinkResponse.timestamp` underflows in Solidity 0.8.x, causing a revert. This doesn't trigger a shutdown (since it reverts before returning false), but it does DoS the price feed until `block.timestamp` catches up to the oracle timestamp.

## Impact

Price feed operations (borrowing, redemptions, liquidations) are temporarily DoS'd for up to 1 hour when API3 returns a future timestamp. While not a permanent issue, this could prevent time-sensitive liquidations during volatile market conditions.

## Code Snippet

[https://github.com/api3dao/contracts/blob/main/contracts/api3-server-v1/DataFeedServer.sol#L30-L38](<https://github.com/api3dao/contracts/blob/main/contracts/api3-server-v1/DataFeedServer.sol#L30-L38>)

```solidity
function _updateDapiWithBeacons(
    bytes32[] memory beaconIds,
    int224[] memory values,
    uint32[] memory timestamps
) internal returns (int224 updatedValue, uint32 updatedTimestamp) {
    // ...
    require(
        timestamp < block.timestamp + 1 hours,  // @audit - allows future timestamps
        "Timestamp not valid"
    );
}
```

[https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/MainnetPriceFeedBase.sol#L114](<https://github.com/sherlock-audit/2025-12-evro-finance-dec-26th/blob/main/evro/contracts/src/PriceFeeds/MainnetPriceFeedBase.sol#L114>)

```solidity
function _isValidChainlinkPrice(ChainlinkResponse memory chainlinkResponse, uint256 _stalenessThreshold)
    internal
    view
    returns (bool)
{
    return chainlinkResponse.success && block.timestamp - chainlinkResponse.timestamp < _stalenessThreshold  // @audit - underflows if timestamp > block.timestamp
        && chainlinkResponse.answer > 0;
}
```

## Recommendation

See their [docs](<https://docs.api3.org/dapps/integration/contract-integration.html#using-timestamp>). Handle future timestamps gracefully by checking before subtraction:

```solidity
function _isValidChainlinkPrice(ChainlinkResponse memory chainlinkResponse, uint256 _stalenessThreshold)
    internal
    view
    returns (bool)
{
    if (!chainlinkResponse.success || chainlinkResponse.answer <= 0) return false;

    // Handle future timestamps from API3 (allowed up to 1 hour ahead)
    if (chainlinkResponse.timestamp > block.timestamp) return true;

    return block.timestamp - chainlinkResponse.timestamp < _stalenessThreshold;
}
```
