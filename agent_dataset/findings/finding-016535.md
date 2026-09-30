---
id: 16535
severity: "High"
---

# Incorrect logic for checking isFillPriceValid

## Description

The logic for calculating if a trader added a valid FillPrice is not correct.

According to the code, when there is a buy order, the target price is less than or equal to the fill price, and when there is a sell order, the target price is greater than or equal to the fill price. Using the above conditions, any trader will not be able to set their target price because the isFillPriceValid will always be false and the trade will not go through. The correct implementation is the opposite of what is currently implemented.
```solidity
function fillOffchainOrders(
        uint128 marketId,
        OffchainOrder.Data[] calldata offchainOrders,
        bytes calldata priceData
    )
        external
        onlyOffchainOrdersKeeper(marketId)
    {
      ............

      ctx.isFillPriceValid = (ctx.isBuyOrder && ctx.offchainOrder.targetPrice <= ctx.fillPriceX18.intoUint256())
            || (!ctx.isBuyOrder && ctx.offchainOrder.targetPrice >= ctx.fillPriceX18.intoUint256());

            // we don't revert here because we want to continue filling other orders.
            if (!ctx.isFillPriceValid) {
                continue;
           }

      .............
    }
```
Traders will not be able to add target price which means they cannot add Take profit or stop loss to their trade
The Offchain order will always fail

## Proof of Concept

Copy the test to test/integration/perpetuals/settlement-branch/fillOffchainOrders/fillOffchainOrders.t.sol

Run the test
```solidity
function testOffChainOrder()
        external
        givenTheSenderIsTheKeeper
        whenThePriceDataIsValid
        whenAllOffchainOrdersHaveAValidSizeDelta
        whenAllTradingAccountsExist
        whenAnOffchainOrdersMarketIdIsEqualToTheProvidedMarketId
        whenAllOffchainOrdersNoncesAreEqualToTheTradingAccountsNonces
    {

     MarketConfig memory fuzzMarketConfig = getFuzzMarketConfig(BTCUSDMARKET_ID);

      uint256 initialMarginRate = 1000e18;

      initialMarginRate = bound({ x: initialMarginRate, min: fuzzMarketConfig.imr, max: MAXMARGINREQUIREMENTS });
      uint256 marginValueUsd = 100000e18;
      marginValueUsd = bound({
            x: marginValueUsd,
            min: USDCMINDEPOSIT_MARGIN,
            max: convertUd60x18ToTokenAmount(address(usdc), USDCDEPOSITCAP_X18)
        });

        deal({ token: address(usdc), to: users.naruto.account, give: marginValueUsd });
        uint128 tradingAccountId = createAccountAndDeposit(marginValueUsd, address(usdc));
        int128 sizeDelta = fuzzOrderSizeDelta(
            FuzzOrderSizeDeltaParams({
                tradingAccountId: tradingAccountId,
                marketId: fuzzMarketConfig.marketId,
                settlementConfigurationId: SettlementConfiguration.MARKETORDERCONFIGURATION_ID,
                initialMarginRate: ud60x18(initialMarginRate),
                marginValueUsd: ud60x18(marginValueUsd),
                maxSkew: ud60x18(fuzzMarketConfig.maxSkew),
                minTradeSize: ud60x18(fuzzMarketConfig.minTradeSize),
                price: ud60x18(fuzzMarketConfig.mockUsdPrice),
                isLong: true,
                shouldDiscountFees: true
            })
        );

        uint128 markPrice = perpsEngine.getMarkPrice(
            fuzzMarketConfig.marketId, fuzzMarketConfig.mockUsdPrice, sizeDelta
        ).intoUint128();

        uint128 targetPrice = 200000e18;

        bytes32 salt = bytes32(block.prevrandao);

        bytes32 digest = keccak256(
            abi.encodePacked(
                "\x19\x01",
                perpsEngine.DOMAIN_SEPARATOR(),
                keccak256(
                    abi.encode(
                        Constants.CREATEOFFCHAINORDER_TYPEHASH,
                        tradingAccountId,
                        fuzzMarketConfig.marketId,
                        sizeDelta,
                        targetPrice,
                        false,
                        uint120(0),
                        salt
                    )
                )
            )
        );

        (uint8 v, bytes32 r, bytes32 s) = vm.sign({ privateKey: users.naruto.privateKey, digest: digest });

        OffchainOrder.Data[] memory offchainOrders = new OffchainOrder.Data[](1);

        offchainOrders[0] = OffchainOrder.Data({
            tradingAccountId: tradingAccountId,
            marketId: fuzzMarketConfig.marketId,
            sizeDelta: sizeDelta,
            targetPrice: targetPrice,
            shouldIncreaseNonce: false,
            nonce: 0,
            salt: salt,
            v: v,
            r: r,
            s: s
        });

        bytes memory mockSignedReport =
            getMockedSignedReport(fuzzMarketConfig.streamId, fuzzMarketConfig.mockUsdPrice);
        address offchainOrdersKeeper = OFFCHAINORDERSKEEPER_ADDRESS;

        changePrank({ msgSender: offchainOrdersKeeper });

        perpsEngine.fillOffchainOrders(fuzzMarketConfig.marketId, offchainOrders, mockSignedReport);

    }
```
The above test does not fail but the order does not get completed, since the isFillPriceValid is false, it just skips the order and moves to the next offchain order.

## Recommendation

Change the condition to when there is a buy order, the target price is greater than or equal to the fill price, and when there is a sell order, the target price is less than or equal to the fill price.
```diff
function fillOffchainOrders(
        uint128 marketId,
        OffchainOrder.Data[] calldata offchainOrders,
        bytes calldata priceData
    )
        external
        onlyOffchainOrdersKeeper(marketId)
    {
      ............
ctx.isFillPriceValid = (ctx.isBuyOrder && ctx.offchainOrder.targetPrice <= ctx.fillPriceX18.intoUint256())
|| (!ctx.isBuyOrder && ctx.offchainOrder.targetPrice >= ctx.fillPriceX18.intoUint256());
ctx.isFillPriceValid = (ctx.isBuyOrder && ctx.offchainOrder.targetPrice >= ctx.fillPriceX18.intoUint256())
|| (!ctx.isBuyOrder && ctx.offchainOrder.targetPrice <= ctx.fillPriceX18.intoUint256());

            // we don't revert here because we want to continue filling other orders.
            if (!ctx.isFillPriceValid) {
                continue;
           }

      .............
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains an incorrect validation routine for off‑chain order execution, specifically the isFillPriceValid check inside the fillOffchainOrders function. The routine is intended to ensure that a trader’s target price (used for take‑profit or stop‑loss) is compatible with the market fill price at the moment the order is processed. However, the logic is inverted: for a buy order the code requires the target price to be less than or equal to the fill price, and for a sell order it requires the target price to be greater than or equal to the fill price. In a typical trading scenario the opposite relationship is required – a buyer wants the fill price to be at or below the target price, and a seller wants the fill price to be at or above the target price. Because of this reversal the condition evaluates to false for any realistic combination of fill price and target price, causing ctx.isFillPriceValid to be false for every order. The function does not revert when the check fails; it simply continues to the next order, so the failing order is silently skipped. As a result, traders are unable to set effective take‑profit or stop‑loss levels; off‑chain orders that include a target price never complete, and users see no execution or error messages, only the absence of the expected trade. The impact is that funds remain locked in the trader’s account without the intended protective or profit‑taking actions, breaking the business logic that assumes a valid target price will trigger an order. This bug manifests whenever an off‑chain order is submitted with a non‑zero target price, regardless of market direction, and it affects any user who relies on the off‑chain order mechanism, including market makers and liquidity providers. The issue was discovered during a security audit by CodeHawks, where the test suite showed that orders were being skipped without a revert, indicating a logical flaw rather than a runtime exception. The problem is subtle because the contract’s control flow does not raise an error, making the failure easy to miss in standard tests that only check for reverts. To remediate the issue, the comparison operators must be inverted: for buy orders the target price should be greater than or equal to the fill price, and for sell orders the target price should be less than or equal to the fill price. This correction restores the intended validation, allowing off‑chain orders with proper target prices to be executed and re‑establishes the expected accounting guarantees of the protocol.
