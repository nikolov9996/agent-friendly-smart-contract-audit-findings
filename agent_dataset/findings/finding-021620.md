---
id: 21620
severity: "High"
---

# Impossible to liquidate accounts with multiple active markets as `LiquidationBranch::liquidateAccounts` reverts due to corruption of ordering in `TradingAccount::activeMarketsIds`

## Description

`LiquidationBranch::liquidateAccounts` iterates through the active markets of the account being liquidated, assuming that the ordering of these active markets will remain constant:
```solidity
// load open markets for account being liquidated
ctx.amountOfOpenPositions = tradingAccount.activeMarketsIds.length();

// iterate through open markets
for (uint256 j = 0; j < ctx.amountOfOpenPositions; j++) {
    // load current active market id into working data
    // @audit assumes constant ordering of active markets
    ctx.marketId = tradingAccount.activeMarketsIds.at(j).toUint128();

    PerpMarket.Data storage perpMarket = PerpMarket.load(ctx.marketId);
    Position.Data storage position = Position.load(ctx.tradingAccountId, ctx.marketId);

    ctx.oldPositionSizeX18 = sd59x18(position.size);
    ctx.liquidationSizeX18 = unary(ctx.oldPositionSizeX18);

    ctx.markPriceX18 = perpMarket.getMarkPrice(ctx.liquidationSizeX18, perpMarket.getIndexPrice());

    ctx.fundingRateX18 = perpMarket.getCurrentFundingRate();
    ctx.fundingFeePerUnitX18 = perpMarket.getNextFundingFeePerUnit(ctx.fundingRateX18, ctx.markPriceX18);

    perpMarket.updateFunding(ctx.fundingRateX18, ctx.fundingFeePerUnitX18);
    position.clear();

    // @audit this calls `EnumerableSet::remove` which changes the order of `activeMarketIds`
    tradingAccount.updateActiveMarkets(ctx.marketId, ctx.oldPositionSizeX18, SD_ZERO);
```
However this is not true as `activeMarketIds` is an `EnumerableSet` which explicitly provides [no guarantees](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/structs/EnumerableSet.sol#L16) that the order of elements is [preserved](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/structs/EnumerableSet.sol#L131-L141) and its `remove` function uses the [swap-and-pop](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/structs/EnumerableSet.sol#L89-L91) method for performance reasons which *guarantees* that order will be corrupted when an active market is removed.
When a trading account has multiple open markets, during liquidation once the first open market is closed the ordering of the account's `activeMarketIds` will be corrupted. This results in the liquidation transaction reverting with `panic: array out-of-bounds access` when attempting to remove the last active market.
Hence it is impossible to liquidate users with multiple active markets; a user can make themselves impossible to liquidate by having positions in multiple active markets.

## Proof of Concept

Add the following helper function to `test/Base.t.sol`:
```solidity
function openManualPosition(
    uint128 marketId,
    bytes32 streamId,
    uint256 mockUsdPrice,
    uint128 tradingAccountId,
    int128 sizeDelta
) internal {
    perpsEngine.createMarketOrder(
        OrderBranch.CreateMarketOrderParams({
            tradingAccountId: tradingAccountId,
            marketId: marketId,
            sizeDelta: sizeDelta
        })
    );

    bytes memory mockSignedReport = getMockedSignedReport(streamId, mockUsdPrice);

    changePrank({ msgSender: marketOrderKeepers[marketId] });

    // fill first order and open position
    perpsEngine.fillMarketOrder(tradingAccountId, marketId, mockSignedReport);

    changePrank({ msgSender: users.naruto });
}
```
Then add the PoC function to `test/integration/perpetuals/liquidation-branch/liquidateAccounts.t.sol`:
```solidity
function test_ImpossibleToLiquidateAccountWithMultipleMarkets() external {
    // give naruto some tokens
    uint256 USER_STARTING_BALANCE = 100_000e18;
    int128  USER_POS_SIZE_DELTA   = 10e18;
    deal({ token: address(usdToken), to: users.naruto, give: USER_STARTING_BALANCE });

    // naruto creates a trading account and deposits their tokens as collateral
    changePrank({ msgSender: users.naruto });
    uint128 tradingAccountId = createAccountAndDeposit(USER_STARTING_BALANCE, address(usdToken));

    // naruto opens first position in BTC market
    openManualPosition(BTC_USD_MARKET_ID, BTC_USD_STREAM_ID, MOCK_BTC_USD_PRICE, tradingAccountId, USER_POS_SIZE_DELTA);

    // naruto opens second position in ETH market
    openManualPosition(ETH_USD_MARKET_ID, ETH_USD_STREAM_ID, MOCK_ETH_USD_PRICE, tradingAccountId, USER_POS_SIZE_DELTA);

    // make BTC position liquidatable
    updateMockPriceFeed(BTC_USD_MARKET_ID, MOCK_BTC_USD_PRICE/2);

    // make ETH position liquidatable
    updateMockPriceFeed(ETH_USD_MARKET_ID, MOCK_ETH_USD_PRICE/2);

    // verify naruto can now be liquidated
    uint128[] memory liquidatableAccountsIds = perpsEngine.checkLiquidatableAccounts(0, 1);
    assertEq(1, liquidatableAccountsIds.length);
    assertEq(tradingAccountId, liquidatableAccountsIds[0]);

    // attempt to liquidate naruto
    changePrank({ msgSender: liquidationKeeper });

    // this reverts with "panic: array out-of-bounds access"
    // due to the order of `activeMarketIds` being corrupted by
    // the removal of the first active market then when attempting
    // to remove the second active market it triggers this error
    perpsEngine.liquidateAccounts(liquidatableAccountsIds, users.settlementFeeRecipient);

    // comment out the ETH position above it no longer reverts since
    // then user would only have 1 active market
    //
    // comment out the following line from `LiquidationBranch::liquidateAccounts`
    // and it also won't revert since the active market removal won't happen:
    //
    // tradingAccount.updateActiveMarkets(ctx.marketId, ctx.oldPositionSizeX18, SD_ZERO);
}
```
Run with: `forge test --match-test test_ImpossibleToLiquidateAccountWithMultipleMarkets`

## Recommendation

Use a data structure that preserves order to store trading account's active market ids.
Alternatively in `LiquidationBranch::liquidateAccounts`, don't remove the active market ids inside the `for` loop but remove them after the `loop` has finished. This will result in a consistent iteration order over the active markets during the `for` loop.
Another option is to get a memory copy by calling `EnumerableSet::values` and iterate over the memory copy instead of storage, eg:
```diff
- ctx.marketId = tradingAccount.activeMarketsIds.at(j).toUint128();
+ ctx.marketId = activeMarketIdsCopy[j].toUint128();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the liquidation routine that iterates over a trader's active market identifiers while assuming the list order stays constant throughout the loop. The contract stores these identifiers in an OpenZeppelin EnumerableSet, a data structure that deliberately does not guarantee element ordering and whose remove operation uses a swap‑and‑pop technique. When the liquidation code closes a position, it calls a function that removes the corresponding market id from the set. This removal instantly reshuffles the remaining ids, breaking the original ordering. Because the outer for‑loop still indexes the set based on its original length, the next iteration may read an index that no longer exists, causing an out‑of‑bounds panic and reverting the whole liquidation transaction. The bug manifests only when an account holds positions in more than one market; a single‑market account liquidates correctly, making the problem easy to miss during casual testing. An attacker (or any user) can open positions in two or more markets, let the positions become under‑collateralised, and then trigger liquidation. The protocol will attempt to liquidate but will revert, leaving the positions open and the account effectively immune to forced closure. This defeats the core risk‑management assumption that under‑collateralised accounts can always be liquidated, potentially allowing unsafe positions to persist and exposing the system to systemic loss. The issue was discovered during a formal audit when the auditors added a test that opened two manual positions and observed a panic with the message "array out‑of‑bounds access" during liquidation. From a user perspective the liquidation transaction simply fails, the UI may show an error or no change in balances, and the trader sees their positions remain despite being flagged as liquidatable. The root cause is the misuse of an unordered set for ordered iteration. To remediate, the contract should either replace the EnumerableSet with a data structure that preserves order, defer removal of market ids until after the iteration completes, or copy the set contents into a memory array and iterate over that immutable snapshot. Any of these approaches restores a stable iteration order and prevents the revert, re‑enabling reliable liquidation of multi‑market accounts.
