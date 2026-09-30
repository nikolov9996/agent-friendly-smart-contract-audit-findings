---
id: 16536
severity: "High"
---

# Market Disruption and Financial Loss Post-Liquidation

## Description

This report identifies a critical vulnerability in the liquidation process of Zaros, which leads to Denial of Service (DoS) and disruption of the market interests and metrics, affecting traders' positions and causing potential financial losses.

Root Cause  
Liquidating an account sets openInterest and skew to zero for that marketId. This occurs due to the liquidateAccounts not adding value to the new OI and skew before the updateOpenInterest call.

<https://github.com/Cyfrin/2024-07-zaros/blob/d687fe96bb7ace8652778797052a38763fbcbb1b/src/perpetuals/branches/LiquidationBranch.sol#L209>

```solidity
// update perp market's open interest and skew; we don't enforce open
// interest and skew caps during liquidations as:
// 1) open interest and skew are both decreased by liquidations
// 2) we don't want liquidation to be DoS'd in case somehow those cap
//    checks would fail
perpMarket.updateOpenInterest(ctx.newOpenInterestX18, ctx.newSkewX18);
```

Note that the comment above this function indicates the devs intend to avoid DoS during liquidation by skipping open interest and skew caps. However, the current implementation incorrectly sets skew and OI to zero instead.

This means in order to reproduce this vulnerability, we only need to liquidate one account and the protocol will have its OI and skew set to zero.

This disrupts the protocol interests, positions, and fees as the following components rely on skew and OI:  
fundingVelocity:

```solidity
function getCurrentFundingVelocity(Data storage self) internal view returns (SD59x18) {
    SD59x18 maxFundingVelocity = sd59x18(uint256(self.configuration.maxFundingVelocity).toInt256());
    SD59x18 skewScale = sd59x18(uint256(self.configuration.skewScale).toInt256());

    SD59x18 skew = sd59x18(self.skew);

    if (skewScale.isZero()) {
        return SD59x18_ZERO;
    }

    SD59x18 proportionalSkew = skew.div(skewScale);
    SD59x18 proportionalSkewBounded = Math.min(Math.max(unary(SDUNIT), proportionalSkew), SDUNIT);

    return proportionalSkewBounded.mul(maxFundingVelocity);
}
```

fundingRate

```solidity
function getCurrentFundingRate(Data storage self) internal view returns (SD59x18) {
    return sd59x18(self.lastFundingRate).add(
        getCurrentFundingVelocity(self).mul(getProportionalElapsedSinceLastFunding(self).intoSD59x18())
    );
}
```

getOrderFeeUsd

```solidity
function getOrderFeeUsd(
        Data storage self,
        SD59x18 sizeDelta,
        UD60x18 markPriceX18
    )
        internal
        view
        returns (UD60x18 orderFeeUsd)
    {
        // isSkewGtZero = true,  isBuyOrder = true,  skewIsZero = false -> taker
        // isSkewGtZero = true,  isBuyOrder = false, skewIsZero = false -> maker
        // isSkewGtZero = false, isBuyOrder = true,  skewIsZero = true  -> taker
        // isSkewGtZero = false, isBuyOrder = false, skewIsZero = true  -> taker
        // isSkewGtZero = false, isBuyOrder = true,  skewIsZero = false -> maker

        // get current skew int128 -> SD59x18
        SD59x18 skew = sd59x18(self.skew);

        // apply new order's skew to current skew
        SD59x18 newSkew = skew.add(sizeDelta);
```

lastFundingFeePerUnit

```solidity
// @audit getNextFundingFeePerUnit is incorrect due to skew 0 impact the getCurrentFundingVelocity
ctx.fundingFeePerUnitX18 = perpMarket.getNextFundingFeePerUnit(ctx.fundingRateX18, ctx.markPriceX18);

// update funding rates for this perpetual market
perpMarket.updateFunding(ctx.fundingRateX18, ctx.fundingFeePerUnitX18);
```

getAccruedFunding

```solidity
function getAccruedFunding(
        Data storage self,
        SD59x18 fundingFeePerUnit
    )
        internal
        view
        returns (SD59x18 accruedFundingUsdX18)
    {
        SD59x18 netFundingFeePerUnit = fundingFeePerUnit.sub(sd59x18(self.lastInteractionFundingFeePerUnit));
        accruedFundingUsdX18 = sd59x18(self.size).mul(netFundingFeePerUnit);
    }
```

```solidity
function getMarkPrice(
        Data storage self,
        SD59x18 skewDelta,
        UD60x18 indexPriceX18
    )
        internal
        view
        returns (UD60x18 markPrice)
    {
        SD59x18 skewScale = sd59x18(self.configuration.skewScale.toInt256());
        SD59x18 skew = sd59x18(self.skew);

        SD59x18 priceImpactBeforeDelta = skew.div(skewScale);
        SD59x18 newSkew = skew.add(skewDelta);
```

At this moment the protocol:  
Lost the imbalance among short/long positions. a.k.a skew  
Lost the OI for short/long positions.

Returns the wrong price for the orderFee in USD and getMarkPrice  
Lost the current interests metrics(fundingRate, fundingFeePerUnit)

Additionally, this will also cause a DoS in the system for positions that need to be updated, halting the market activity for those positions. I.e: Bob has an open position for the BTC market and he wants to increase his margin value, system will revert due to the following:

As openInterest is 0 and checkOpenInterestLimits is used on fillOrder, it will try to sub the oldPosition value from the currentOpenInterest causing an underflow.  
<https://github.com/Cyfrin/2024-07-zaros/blob/d687fe96bb7ace8652778797052a38763fbcbb1b/src/perpetuals/leaves/PerpMarket.sol#L286-L294>

```solidity
UD60x18 maxOpenInterest = ud60x18(self.configuration.maxOpenInterest);
UD60x18 currentOpenInterest = ud60x18(self.openInterest);

// calculate new open interest which would result from proposed trade
// by subtracting old position size then adding new position size to
// current open interest
newOpenInterest =
    currentOpenInterest.sub(oldPositionSize.abs().intoUD60x18()).add(newPositionSize.abs().intoUD60x18());
```

DoS - Position updates halted due to arithmetic underflow.  
Market metrics/calculation disrupted: Disrupted skew and open interest calculations impact the core financial metrics like fundingRate, fundingFeePerUnit, markPrice, getAccruedFunding and getOrderFeeUsd.  
Users from that market will lose their interest.  
Users not originally at risk may face liquidation due to loss of earnings and interests.

## Proof of Concept

There are two tests on the PoC below.

One reproduces the DoS and the other shows the incorrect values set to the variables mentioned above.  
Setup: add the following code on liquidateAccounts.t.sol and run forge test --match-test testGiveOneAccountIsLiquidated_ -vv

```solidity
// import "forge-std/console.sol";
function testGiveOneAccountIsLiquidatedsystemWillSetIncorrectValueForSkewAndInterestcausingDoS_whenUserTryToUpdateHisPosition()
    external
    givenTheSenderIsARegisteredLiquidator
    whenTheAccountsIdsArrayIsNotEmpty
    givenAllAccountsExist
{
    // pre condition - setup market conditions.
    TestFuzzGivenThereAreLiquidatableAccountsInTheArrayContext memory ctx = _setupMarketConditions(10);

    // action - create 10+ long equal positions and liquidate only one
    // result: skew and OI == 0 after liquidation. 
    createOrdersAndLiquidateAccountssettingTheSkewAndOI_toZero(ctx, true, 10);
    _assertSkewAndOIasZero(ctx.fuzzMarketConfig.marketId);

    // action 2 - update the market with 2 shorts and 1 long position, liquidate 1 short.
    // result: skew and OI == 0 after liquidation again.
    changePrank({ msgSender: users.naruto.account });
    uint128 accountIdToBeUpdated = createTwoShortPositionsOneLongPosition_AndLiquidateOneShortPosition(ctx);
    _assertSkewAndOIasZero(ctx.fuzzMarketConfig.marketId);

    // Impact: DoS when updating the position while the skew and open interest are set to zero.

    // DOS - [FAIL. Reason: panic: arithmetic underflow or overflow (0x11)] due to currentOpenInterest = 0.
    // https://github.com/Cyfrin/2024-07-zaros/blob/c97c68664048f251de8fab1e55a034bcd3df1ec9/src/perpetuals/leaves/PerpMarket.sol#L292-L293
    changePrank({ msgSender: users.naruto.account });
    _updateExistingPosition(ctx.fuzzMarketConfig, accountIdToBeUpdated, ctx.initialMarginRate, ctx.accountMarginValueUsd, true);   
}

function testGiveOneAccountIsLiquidatedtheProtocolIsDisrupteddueToWrongOIandSkew() 
    external
    givenTheSenderIsARegisteredLiquidator
    givenAllAccountsExist 
{ 
    // pre condition - open 2 positions
    uint256 marginValueUsdc = 100_000e6;
    int128 userPositionSizeDelta = 10e18;
    
    deal({ token: address(usdc), to: users.naruto.account, give: marginValueUsdc * 2 });
    // naruto creates a trading account and deposits their tokens as collateral
    changePrank({ msgSender: users.naruto.account });
    uint128 tradingAccountId = createAccountAndDeposit(marginValueUsdc, address(usdc));
    // naruto opens first position in BTC market

    printSkewAndInterest(BTCUSDMARKETID);

    openManualPosition(
        BTCUSDMARKETID, BTCUSDSTREAMID, MOCKBTCUSD_PRICE, tradingAccountId, userPositionSizeDelta
    );
    
    skip(1 hours);

    console.log("skew and OI after the first long position being opened");
    printSkewAndInterest(BTCUSDMARKETID);

    // fetch the correct price for the market properties
    SD59x18 sizeDelta = sd59x18(userPositionSizeDelta);
    uint256 correctFundingTime = block.timestamp;
    UD60x18 correctMarkPriceX18 = perpsEngine.getMarkPrice(
        BTCUSDMARKETID, MOCKBTCUSDPRICE, sizeDelta.intoInt256()
    );

    uint256 correctOrderFeeInUsd = perpsEngine.exposedgetOrderFeeUsd(BTCUSDMARKETID, sizeDelta, correctMarkPriceX18).intoUint128();
    SD59x18 correctFundingRateX18 = perpsEngine.getFundingRate(BTCUSDMARKET_ID);
    SD59x18 correctNextFundingFeePerUnit = perpsEngine.exposed_getNextFundingFeePerUnit(
        BTCUSDMARKET_ID, correctFundingRateX18, correctMarkPriceX18
    );

    // print all the values above
    console.log("one open position mark price: %e", correctMarkPriceX18.intoUint256());
    console.log("one open position order fee in usd: %e", correctOrderFeeInUsd);
    console.log("one open position funding rate x18: %e", correctFundingRateX18.intoInt256());
    console.log("one open position next funding fee per unit: %e", correctNextFundingFeePerUnit.intoInt256());
    console.log("");

    uint128 tradingAccountId2 = createAccountAndDeposit(marginValueUsdc, address(usdc));
    // naruto opens 2nd position in BTC market
    openManualPosition(
        BTCUSDMARKETID, BTCUSDSTREAMID, MOCKBTCUSD_PRICE, tradingAccountId2, userPositionSizeDelta
    );

    skip(1 hours);

    console.log("skew and OI after the second long position being opened");
    printSkewAndInterest(BTCUSDMARKETID);

    correctMarkPriceX18 = perpsEngine.getMarkPrice(
        BTCUSDMARKETID, MOCKBTCUSDPRICE, sizeDelta.intoInt256()
    );
    correctOrderFeeInUsd = perpsEngine.exposedgetOrderFeeUsd(BTCUSDMARKETID, sizeDelta, correctMarkPriceX18).intoUint128();
    correctFundingRateX18 = perpsEngine.getFundingRate(BTCUSDMARKET_ID);
    correctNextFundingFeePerUnit = perpsEngine.exposed_getNextFundingFeePerUnit(
        BTCUSDMARKET_ID, correctFundingRateX18, correctMarkPriceX18
    );

    // values with 2 open positions...
    console.log("two open positions mark price: %e", correctMarkPriceX18.intoUint256());
    console.log("two open positions order fee in usd: %e", correctOrderFeeInUsd);
    console.log("two open positions funding rate x18: %e", correctFundingRateX18.intoInt256());
    console.log("two open positions next funding fee per unit: %e", correctNextFundingFeePerUnit.intoInt256());
    console.log("");

    updateMockPriceFeed(BTCUSDMARKETID, MOCKBTCUSDPRICE/2);
    _liquidateOneAccount(tradingAccountId2);
    updateMockPriceFeed(BTCUSDMARKETID, MOCKBTCUSDPRICE);

    skip(100 hours);

    console.log("skew and OI after one of the long positions being liquidated");
    printSkewAndInterest(BTCUSDMARKETID);

    correctMarkPriceX18 = perpsEngine.getMarkPrice(
        BTCUSDMARKETID, MOCKBTCUSDPRICE, sizeDelta.intoInt256()
    );
    correctOrderFeeInUsd = perpsEngine.exposedgetOrderFeeUsd(BTCUSDMARKETID, sizeDelta, correctMarkPriceX18).intoUint128();
    correctFundingRateX18 = perpsEngine.getFundingRate(BTCUSDMARKET_ID);
    correctNextFundingFeePerUnit = perpsEngine.exposed_getNextFundingFeePerUnit(
        BTCUSDMARKET_ID, correctFundingRateX18, correctMarkPriceX18
    );

    // values with one open position...
    console.log("one open position mark price: %e", correctMarkPriceX18.intoUint256());
    console.log("one open position order fee in usd: %e", correctOrderFeeInUsd);
    console.log("one open position funding rate x18: %e", correctFundingRateX18.intoInt256());
    console.log("one open position next funding fee per unit: %e", correctNextFundingFeePerUnit.intoInt256());
}

// HELPER FUNCTIONS

function _assertSkewAndOIasZero(uint128 marketId) internal { 
    (UD60x18 longsOpenInterest, UD60x18 shortsOpenInterest, UD60x18 totalOpenInterest) = perpsEngine.getOpenInterest(marketId);

    // @audit all the interest rates and skew are set to zero, even though only one small position was liquidated.
    assertEq(0, perpsEngine.getSkew(marketId).intoInt256(), "skew != 0");
    assertEq(0, longsOpenInterest.intoUint256(), "longs open interest != 0"); 
    assertEq(0, shortsOpenInterest.intoUint256(), "shorts open interest != 0");
    assertEq(0, totalOpenInterest.intoUint256(), "total open interest != 0");
}

function createOrdersAndLiquidateAccountssettingTheSkewAndOItoZero(TestFuzzGivenThereAreLiquidatableAccountsInTheArray_Context memory ctx, bool isLong, uint256 amountOfTradingAccounts) internal {
    _createOpenPositions(ctx.fuzzMarketConfig, amountOfTradingAccounts, ctx.initialMarginRate, ctx.accountMarginValueUsd, isLong, ctx.accountsIds);

    // print skew and open interest after opening positions
    _printSkewAndInterest(ctx.fuzzMarketConfig.marketId);

    setAccountsAsLiquidatable(ctx.fuzzMarketConfig, isLong);

    ctx.nonLiquidatableTradingAccountId = createAccountAndDeposit(ctx.accountMarginValueUsd, address(usdz));
    ctx.accountsIds[amountOfTradingAccounts] = ctx.nonLiquidatableTradingAccountId;

    ctx.expectedLastFundingRate = perpsEngine.getFundingRate(ctx.fuzzMarketConfig.marketId).intoInt256();
    ctx.expectedLastFundingTime = block.timestamp;

    _liquidateOneAccount(ctx.accountsIds[2]); // liquidate a random account.
    skip(1 hours);
}

function createTwoShortPositionsOneLongPositionAndLiquidateOneShortPosition(TestFuzzGivenThereAreLiquidatableAccountsInTheArray_Context memory ctx) internal returns(uint128 accountIdToBeUpdated) {
    // create 2 short positions
    console.log("adding 2 short positions...");
    uint128 accountIdToLiquidate = _createSingularPosition(ctx.fuzzMarketConfig, ctx.initialMarginRate, ctx.accountMarginValueUsd, false);
    accountIdToBeUpdated = _createSingularPosition(ctx.fuzzMarketConfig, ctx.initialMarginRate, ctx.accountMarginValueUsd, false);
    console.log("added... ");
    console.log("");

    // create 1 long position
    console.log("adding 1 long position...");
    _createSingularPosition(ctx.fuzzMarketConfig, ctx.initialMarginRate, ctx.accountMarginValueUsd, true);
    console.log("added... ");
    console.log("");
    
    // skew != 0
    _printSkewAndInterest(ctx.fuzzMarketConfig.marketId);

    // make liquidation possible
    setAccountsAsLiquidatable(ctx.fuzzMarketConfig, false);
    ctx.expectedLastFundingRate = perpsEngine.getFundingRate(ctx.fuzzMarketConfig.marketId).intoInt256();
    ctx.expectedLastFundingTime = block.timestamp;

    // liquidate only one short position
    console.log("liquidating one short position: %d ...", accountIdToLiquidate);
    _liquidateOneAccount(accountIdToLiquidate); // liquidate a random account.
    console.log("liquidated...");
    console.log("");

    skip(1 hours);
}

function _createOpenPositions(MarketConfig memory marketConfig, uint256 numberOfAccounts, uint256 initialMarginRate, uint256 margin, bool isLong, uint128[] memory accountIds) internal { 
    for (uint128 i; i < numberOfAccounts; i++) {
        accountIds[i] = _createSingularPosition(marketConfig, initialMarginRate, margin, isLong);
    }
}

function _createSingularPosition(MarketConfig memory marketConfig, uint256 initialMarginRate, uint256 margin, bool isLong) internal returns (uint128 tradingAccountId) { 
    deal({ token: address(usdz), to: users.naruto.account, give: margin });
    tradingAccountId = createAccountAndDeposit(margin, address(usdz));
    openPosition(marketConfig, tradingAccountId, initialMarginRate, margin, isLong);
}

function _updateExistingPosition(MarketConfig memory marketConfig, uint128 tradingAccountId, uint256 initialMarginRate, uint256 margin, bool isLong) internal { 
    deal({ token: address(usdz), to: users.naruto.account, give: margin });
    perpsEngine.depositMargin(tradingAccountId, address(usdz), margin);
    openPosition(marketConfig, tradingAccountId, initialMarginRate, margin, isLong);
}

function setupMarketConditions(uint256 amountOfTradingAccounts) internal returns(TestFuzzGivenThereAreLiquidatableAccountsInTheArray_Context memory ctx) { 
    // Pre conditions - Setup market conditions
    uint256 marketId = 1;
    ctx.fuzzMarketConfig = getFuzzMarketConfig(marketId);
    ctx.marginValueUsd = 10_000e18 / amountOfTradingAccounts;
    ctx.initialMarginRate = ctx.fuzzMarketConfig.imr;
    ctx.accountsIds = new uint128[](amountOfTradingAccounts + 2);
    ctx.accountMarginValueUsd = ctx.marginValueUsd / (amountOfTradingAccounts + 1);
}

function _liquidateOneAccount(uint128 tradingAccountId) internal { 
    changePrank({ msgSender: liquidationKeeper });
    skip(1 hours);

    uint128[] memory liquidableAccountIds = new uint128[](1);
    liquidableAccountIds[0] = tradingAccountId;
    perpsEngine.liquidateAccounts(liquidableAccountIds);
}

function _printSkewAndInterest(uint128 marketId) internal { 
    console.log("--------------------");
    console.log("skew: %e",  perpsEngine.getSkew(marketId).intoInt256());
    (UD60x18 longsOpenInterest, UD60x18 shortsOpenInterest, UD60x18 totalOpenInterest) = perpsEngine.getOpenInterest(marketId);
    console.log("longs open interest: %e",  longsOpenInterest.intoUint256());
    console.log("shorts open interest: %e",  shortsOpenInterest.intoUint256());
    console.log("total open interest: %e",  totalOpenInterest.intoUint256());
    console.log("--------------------");
    console.log("");
}
```

Output:

JavaScript
--------------------
  skew: 0e0
  longs open interest: 0e0
  shorts open interest: 0e0
  total open interest: 0e0
  --------------------
  
  skew and OI after the first long position being opened
  --------------------
  skew: 1e19
  longs open interest: 1e19
  shorts open interest: 0e0
  total open interest: 1e19
  --------------------
  
  one open position mark price: 1.0000015e23
  one open position order fee in usd: 8.000012e20
  one open position funding rate x18: 1.249999999e9
  one open position next funding fee per unit: -2.604170506249e12
  
  skew and OI after the second long position being opened
  --------------------
  skew: 2e19
  longs open interest: 2e19
  shorts open interest: 0e0
  total open interest: 2e19
  --------------------
  
  two open positions mark price: 1.0000025e23
  two open positions order fee in usd: 8.00002e20
  two open positions funding rate x18: 3.749999998e9
  two open positions next funding fee per unit: -1.3020863147915e13
  
  skew and OI after one of the long positions being liquidated
  --------------------
  skew: 0e0
  longs open interest: 0e0
  shorts open interest: 0e0
  total open interest: 0e0
  --------------------
  
  one open position mark price: 1.0000005e23
  one open position order fee in usd: 8.000004e20
  one open position funding rate x18: 6.249999998e9
  one open position next funding fee per unit: -2.62239716177708e15

Suite result: FAILED. 1 passed; 1 failed; 0 skipped; finished in 17.72ms (13.20ms CPU time)

Ran 1 test suite in 123.60ms (17.72ms CPU time): 1 tests passed, 1 failed, 0 skipped (2 total tests)

Failing tests:  
Encountered 1 failing test in test/integration/perpetuals/liquidation-branch/liquidateAccounts/liquidateAccounts.t.sol:LiquidateAccountsIntegrationTest  
[FAIL. Reason: panic: arithmetic underflow or overflow (0x11)] testGiveOneAccountIsLiquidatedsystemWillSetIncorrectValueForSkewAndInterestcausingDoS_whenUserTryToUpdateHisPosition() (gas: 13239744)

## Recommendation

Update skew and OI by deducting only the liquidated position. This clears the impact of liquidated positions from open interest and skew without resetting them to zero or causing reverts.

Add the following function to PerpMarket.sol

```diff
/// @notice Clears out liquidation open interest state for the given market.
function updateOpenInterestLiquidation(Data storage self, SD59x18 oldPositionSize) internal {
    UD60x18 currentOpenInterest = ud60x18(self.openInterest);
    SD59x18 currentSkew = sd59x18(self.skew);
    self.openInterest = currentOpenInterest.sub(oldPositionSize.abs().intoUD60x18()).intoUint128();
    self.skew = currentSkew.sub(oldPositionSize).intoInt256().toInt128();
}
```

Now on the liquidateAccounts function, replace the call to updateOpenInterest with the function above.

```diff
perpMarket.updateOpenInterest(ctx.newOpenInterestX18, ctx.newSkewX18);
perpMarket.updateOpenInterestLiquidation(ctx.oldPositionSizeX18);
```

Run the PoC again, but this time comment out calls to _assertSkewAndOIasZero().

✅ Result: No DoS and the skew/OI values are adjusted correctly.

JavaScript
--------------------
  skew: 0e0
  longs open interest: 0e0
  shorts open interest: 0e0
  total open interest: 0e0
  --------------------
  
  skew and OI after the first long position being opened
  --------------------
  skew: 1e19
  longs open interest: 1e19
  shorts open interest: 0e0
  total open interest: 1e19
  --------------------
  
  one open position mark price: 1.0000015e23
  one open position order fee in usd: 8.000012e20
  one open position funding rate x18: 1.249999999e9
  one open position next funding fee per unit: -2.604170506249e12
  
  skew and OI after the second long position being opened
  --------------------
  skew: 2e19
  longs open interest: 2e19
  shorts open interest: 0e0
  total open interest: 2e19
  --------------------
  
  two open positions mark price: 1.0000025e23
  two open positions order fee in usd: 8.00002e20
  two open positions funding rate x18: 3.749999998e9
  two open positions next funding fee per unit: -1.3020863147915e13
  
  skew and OI after one of the long positions being liquidated
  --------------------
  skew: 1e19
  longs open interest: 1e19
  shorts open interest: 0e0
  total open interest: 1e19
  --------------------
  
  one open position mark price: 1.0000015e23
  one open position order fee in usd: 8.000012e20
  one open position funding rate x18: 1.31249999997e11
  one open position next funding fee per unit: -2.8664105494643746e16
  Suite result: ok. 2 passed; 0 failed; 0 skipped; finished in 17.90ms (13.86ms CPU time)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the liquidation routine of the perpetual market contract. When an account is liquidated the code calls the generic updateOpenInterest function with values that have been calculated without preserving the existing open interest (OI) and skew of the market. Instead of subtracting only the size of the liquidated position, the implementation overwrites the market’s OI and skew with zero. This mistake originates from a comment that intended to bypass cap checks during liquidation, but the actual arithmetic clears the whole state. As a result, after a single liquidation the market reports zero skew, zero total open interest, and consequently all derived metrics – funding velocity, funding rate, mark price, order fee and accrued funding – collapse to zero or incorrect values. Any subsequent attempt to modify a position triggers the open‑interest limit check, which now sees a current OI of zero and attempts to subtract the old position size, causing an arithmetic underflow and a transaction revert. The protocol therefore experiences a denial‑of‑service condition: traders cannot increase margin, cannot open or modify positions, and the funding mechanism stops working. From a user’s perspective the UI would show that the market has no open interest, funding rates are flat, order fees are zero and attempts to trade revert with an “arithmetic underflow” error, effectively making funds appear to disappear or become locked. The issue was discovered during a manual audit and reproduced with a proof‑of‑concept test that liquidated a single account and observed the OI and skew reset to zero, followed by a failing transaction when trying to update a position. The bug is hard to notice because zero values may be interpreted as a dormant market rather than a corrupted state, and the comment in the code masks the intention. The proper fix is to adjust the liquidation path so that it only deducts the liquidated position from the existing OI and skew, preserving the rest of the market state. A dedicated updateOpenInterestLiquidation function can perform the subtraction safely, after which the regular updateOpenInterest call can be retained for other operations. This restores correct funding calculations, prevents underflow, and eliminates the denial‑of‑service scenario, ensuring that traders retain accurate interest, price impact and fee information after liquidations.
