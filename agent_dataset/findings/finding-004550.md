---
id: 4550
severity: "High"
---

# Excessive price staleness buffer allows usage of outdated oracle prices Submitted by 0xTheBlackPanther, also found by kelvinsmart, santipu, zanderbyte, 0xNirix and pkqs90

## Description

```solidity
In the PriceFeed contract, the _isPriceStale() function adds a constant RESPONSE_TIMEOUT_BUFFER of 1 hour to each oracle's heartbeat when determining if a price is stale:
uint256 public constant RESPONSE_TIMEOUT_BUFFER = 1 hours; // @audit-poc
function _isPriceStale(uint256 _priceTimestamp, uint256 _heartbeat) internal view returns (bool isPriceStale) {
    isPriceStale = block.timestamp - _priceTimestamp > _heartbeat + RESPONSE_TIMEOUT_BUFFER;
}
```
This means that for any oracle feed, the actual maximum allowed age of a price is the heartbeat period plus an additional hour. The impact is particularly severe for oracles with short heartbeat periods. Let's take an example:
• An oracle with a 30-minute heartbeat will actually allow prices up to 90 minutes old.
• An oracle with a 15-minute heartbeat will allow prices up to 75 minutes old.
The root cause is the design decision to use a fixed 1-hour buffer regardless of the oracle's heartbeat period. This appears to be inherited from the Prisma codebase but creates a significant discrepancy between intended & actual price freshness guarantees.

Impact Explanation:
High -- This issue can lead to the protocol operating on significantly stale price data, which could be exploited during periods of high volatility:
1. For fast-moving assets like ETH/USD where prices can move >5% in under an hour:
• If ETH is $2000 and drops 10% to $1800 in 45 minutes.
• A 30-minute heartbeat feed would intend to reject the $2000 price after 30 minutes.
• But due to the buffer, the $2000 price could still be used for up to 90 minutes.
• This allows users to interact with the protocol at incorrect prices.
2. Specific attack scenario:
• Attacker monitors for rapid price movements in underlying asset.
• When price drops significantly but oracle's old price is still accepted due to buffer.
• Attacker can mint loans using inflated collateral valuations.
• Once oracle updates, these positions become undercollateralized.
The severity is high because:
• It affects core protocol functionality (price feeds).
• Can lead to direct financial loss.
• Requires no special permissions to exploit
• Most dangerous during market volatility when accurate pricing is most critical

## Proof of Concept

```solidity
Add the test below in test/foundry/core/PriceFeedTest.t.sol and run it. Make sure to add console2 import {console2} from "forge-std/console2.sol";:
function test_StalePriceUsedDueToBuffer() external {
    vm.startPrank(users.owner);
    console2.log("\n=== Initial Setup ===");
    uint256 initialTimestamp = block.timestamp;
    console2.log("Current block timestamp:", initialTimestamp);
    // First set previous round data (round 1)
    mockOracle2.setResponse(
        1, // roundId
        2000e8, // $2000 price
        block.timestamp - 2 minutes, // startedAt
        block.timestamp - 2 minutes, // updatedAt
        1 // answeredInRound
    );
    // Set current round data (round 2) - this price will be stored
    mockOracle2.setResponse(
        2, // roundId
        2000e8, // $2000 price
        block.timestamp, // startedAt
        block.timestamp, // updatedAt
        2 // answeredInRound
    );
    // Set oracle with 30 minute heartbeat
    priceFeed.setOracle(
        address(stakedBTC),
        address(mockOracle2),
        30 minutes, // heartbeat
        bytes4(0), // no share price signature
        18, // decimals
        false // not ETH indexed
    );
    uint256 initialPrice = priceFeed.fetchPrice(address(stakedBTC));
    assertEq(initialPrice, 2000e18, "Initial price should be $2000");
    console2.log("Initial price:", initialPrice / 1e18);
    // Advance time by 85 minutes (> heartbeat but < heartbeat + buffer)
    vm.warp(block.timestamp + 85 minutes);
    console2.log("\nTime advanced by 85 minutes");
    console2.log("New timestamp:", block.timestamp);
    console2.log("Time elapsed:", (block.timestamp - initialTimestamp) / 60, "minutes");
    // Keep the oracle returning the same timestamp for round 2
    mockOracle2.setResponse(
        2, // Same roundId
        2000e8, // Same price
        block.timestamp - 85 minutes, // Old timestamp
        block.timestamp - 85 minutes, // Old timestamp
        2 // Same answeredInRound
    );
    // Get price - should still be valid despite being stale
    uint256 stalePrice = priceFeed.fetchPrice(address(stakedBTC));
    assertEq(stalePrice, 2000e18, "Old price still used due to buffer");
    console2.log("\nStale price still being used:", stalePrice / 1e18);
    console2.log("Price age:", 85, "minutes (> 30min heartbeat but < 90min total timeout)");
    // Now advance just past the buffer
    vm.warp(block.timestamp + 6 minutes);
    console2.log("\nTime advanced by additional 6 minutes");
    console2.log("Total time elapsed:", (block.timestamp - initialTimestamp) / 60, "minutes");
    // Should revert due to truly stale price
    vm.expectRevert(abi.encodeWithSelector(PriceFeed__FeedFrozenError.selector, address(stakedBTC)));
    priceFeed.fetchPrice(address(stakedBTC));
    console2.log("Price finally considered stale and fetchPrice() reverted");
    vm.stopPrank();
}
Result logs:
Ran 1 test for test/foundry/core/PriceFeedTest.t.sol:PriceFeedTest
[PASS] test_StalePriceUsedDueToBuffer() (gas: 100971)
Logs:
=== Initial Setup ===
Current block timestamp: 1659973223
Initial price: 2000
Time advanced by 85 minutes
New timestamp: 1659978323
Time elapsed: 85 minutes
Stale price still being used: 2000
Price age: 85 minutes (> 30min heartbeat but < 90min total timeout)
Time advanced by additional 6 minutes
Total time elapsed: 91 minutes
Price finally considered stale and fetchPrice() reverted
From the logs you can see that even though the oracle's heartbeat is set to 30 minutes, the contract still accepts and uses a stale price after 85 minutes due to the extra 1-hour buffer, allowing potentially outdated price data to be used for an extended period.
```

## Recommendation

```solidity
Implement one of the following solutions:
• Reduce the fixed buffer to a more reasonable duration:
uint256 public constant RESPONSE_TIMEOUT_BUFFER = 15 minutes;
• Or use dynamic buffers based on heartbeat duration:
function _getTimeoutBuffer(uint256 _heartbeat) internal pure returns (uint256) {
    if (_heartbeat < 1 hours) {
        return 15 minutes;
    }
    if (_heartbeat < 4 hours) {
        return 30 minutes;
    }
    return 1 hours;
}
function _isPriceStale(uint256 _priceTimestamp, uint256 _heartbeat) internal view returns (bool) {
    uint256 buffer = _getTimeoutBuffer(_heartbeat);
    return block.timestamp - _priceTimestamp > _heartbeat + buffer;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an excessive price‑staleness buffer in the protocol’s price‑feed component. The contract determines whether a price is stale by comparing the elapsed time since the last oracle update with the oracle’s configured heartbeat plus a constant RESPONSE_TIMEOUT_BUFFER of one hour. Because the buffer is fixed, any oracle – even those that are supposed to provide fresh data every few minutes – is allowed to serve prices that are up to an hour older than intended. The root cause is a design decision inherited from another code base that does not scale the buffer relative to the heartbeat. An attacker can exploit this by monitoring a fast‑moving asset, waiting for a sharp price move, and then interacting with the protocol while the contract still accepts the old, higher price. This enables the attacker to open loans or mint positions with inflated collateral valuations, which become under‑collateralised once the oracle finally updates. The impact is that users may see their collateral value appear unchanged or receive loans at incorrect rates, leading to potential loss of funds, liquidations, or unfair profit for the attacker. The condition occurs whenever the time since the last price update exceeds the heartbeat but remains below heartbeat + 1 hour; during periods of high volatility this window can be critical. All participants that rely on the price feed – borrowers, lenders, and the protocol itself – are affected. The issue was discovered during a security audit that included unit tests reproducing the stale‑price acceptance after advancing time beyond the heartbeat but within the extra hour. It is hard to notice because the contract still returns a valid price and does not emit an obvious warning, so users see normal UI values while the underlying data is outdated. From the user’s perspective the UI may show a stable collateral value or a successful loan execution even though the market price has moved dramatically, violating the expectation that the protocol always uses the latest price. The bug belongs to the class of incorrect time‑window validation or excessive timeout buffer errors that break accounting assumptions about price freshness. The recommended fix is to replace the fixed one‑hour buffer with a smaller constant such as 15 minutes or to compute a dynamic buffer based on the heartbeat, ensuring that the stale‑price check aligns with the intended freshness guarantees.
