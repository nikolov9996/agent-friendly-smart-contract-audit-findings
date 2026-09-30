---
id: 15816
severity: "High"
---

# The `DeliveryPlace::settleAskTaker()` function mistakenly uses `makerInfo.tokenAddress` to update the `TokenBalanceType.PointToken` in the `userTokenBalanceMap` mapping, leading to a critical error.

## Description

The DeliveryPlace::settleAskTaker() function mistakenly uses makerInfo.tokenAddress to update the TokenBalanceType.PointToken in the userTokenBalanceMap mapping, leading to a critical error.

When UserA creates a Bid.offer, the transaction process unfolds as follows:
UserA creates a Bid.offer by calling PreMarkets::createOffer().
UserB calls PreMarkets::createTaker() using the Bid.offer.offerAddr and a specified amount.
The administrator updates the market by calling SystemConfig::updateMarket.
UserB then calls DeliveryPlace::settleAskTaker() to settle the transaction. During this step, UserB transfers mockPointToken to the contract, fulfilling the amount promised in step 2, and updates the balance information in userTokenBalanceMap.

Below is the relevant code from DeliveryPlace::settleAskTaker():
```solidity
    function settleAskTaker(address stock, uint256 settledPoints) external {
        IPerMarkets perMarkets = tadleFactory.getPerMarkets();
        StockInfo memory stockInfo = perMarkets.getStockInfo(_stock);

        (
            OfferInfo memory offerInfo,
            MakerInfo memory makerInfo,
            MarketPlaceInfo memory marketPlaceInfo,
            MarketPlaceStatus status
        ) = getOfferInfo(stockInfo.preOffer);

        // SNIP...

        uint256 settledPointTokenAmount = marketPlaceInfo.tokenPerPoint *
            _settledPoints;
        ITokenManager tokenManager = tadleFactory.getTokenManager();
        if (settledPointTokenAmount > 0) {
            tokenManager.tillIn(
                _msgSender(),
                marketPlaceInfo.tokenAddress,
                settledPointTokenAmount,
                true
            );

            tokenManager.addTokenBalance(
                TokenBalanceType.PointToken,
                offerInfo.authority,
                makerInfo.tokenAddress,
                settledPointTokenAmount
            );
        }
        // SNIP...
    }
```
In the above code, tokenManager.addTokenBalance() incorrectly uses makerInfo.tokenAddress when updating the TokenBalanceType.PointToken balance for the user. Instead, the marketPlaceInfo.tokenAddress should be used. This misstep leads to an incorrect balance being recorded in the userTokenBalanceMap, which could result in serious errors during settlement.

## Proof of Concept

To demonstrate the issue, add the following test code to test/PreMarkets.t.sol and run it:

Note: Before running the PoC, address the issue related to the incorrect permission check in the DeliveryPlace::settleAskTaker() function, where the caller's address is mistakenly validated against the wrong authority.
```solidity
    function testDeliveryPlacesettleAskTakeraddTokenBalanceerror() public {

        ///////////////////////////
        // user create Bid.Offer //
        ///////////////////////////
        vm.prank(user);
        // transfer mockUSDCToken 1e16 to capitalPool
        preMarktes.createOffer(
            CreateOfferParams(
                marketPlace,
                address(mockUSDCToken),
                1000, 
                0.01 * 1e18, 
                12000, 
                300, 
                OfferType.Bid,
                OfferSettleType.Turbo
            )
        );

        // Cache user's offer address
        address offerAddr = GenerateAddress.generateOfferAddress(0);
        ////////////////////////
        // user2 create Taker //
        ////////////////////////
        vm.prank(user2);
        // transfer mockUSDCToken 1.235e16 to capitalPool
        preMarktes.createTaker(offerAddr, 1000);

        // Cache user2's stock address
        address user2StockAddr = GenerateAddress.generateStockAddress(1);

        ////////////////////////
        // admin updateMarket //
        ////////////////////////
        vm.prank(user1);
        systemConfig.updateMarket(
            "Backpack",
            address(mockPointToken),
            0.01 * 1e18,
            block.timestamp - 1,
            3600
        );

        //////////////////////////
        // user2 settleAskTaker //
        //////////////////////////       
        vm.startPrank(user2);
        mockPointToken.approve(address(tokenManager), 10000 * 10 * 18);

        // transfer mockPointToken 1e19 to capitalPool
        deliveryPlace.settleAskTaker(user2StockAddr, 1000);
        vm.stopPrank();

        //////////////////////////
        //  check user balance  //
        //////////////////////////
        // user
        uint256 usermockPointTokenAmount_PointToken = tokenManager.userTokenBalanceMap(
            address(user),
            address(mockPointToken),
            TokenBalanceType.PointToken
        );
        console2.log("usermockPointTokenAmountPointToken:",usermockPointTokenAmountPointToken);

        uint256 usermockUSDCTokenAmount_PointToken = tokenManager.userTokenBalanceMap(
            address(user),
            address(mockUSDCToken),
            TokenBalanceType.PointToken
        );
        console2.log("usermockUSDCTokenAmountPointToke:",usermockUSDCTokenAmountPointToken);
    }
    // [PASS] testDeliveryPlacesettleAskTakeraddTokenBalanceerror() (gas: 1116914)
    //     Logs:
    //     usermockPointTokenAmount_PointToken: 0
    //     usermockUSDCTokenAmount_PointToke: 10000000000000000000
```
The test logs will show that the userTokenBalanceMap was updated incorrectly.

Code Snippet
<https://github.com/Cyfrin/2024-08-tadle/blob/04fd8634701697184a3f3a5558b41c109866e5f8/src/core/DeliveryPlace.sol#L335-L433>

The incorrect use of makerInfo.tokenAddress when updating the TokenBalanceType.PointToken balance in userTokenBalanceMap leads to a serious error

## Recommendation

Please use marketPlaceInfo.tokenAddress when updating the balance for TokenBalanceType.PointToken:
```diff
    function settleAskTaker(address stock, uint256 settledPoints) external {
        IPerMarkets perMarkets = tadleFactory.getPerMarkets();
        StockInfo memory stockInfo = perMarkets.getStockInfo(_stock);

        (
            OfferInfo memory offerInfo,
            MakerInfo memory makerInfo,
            MarketPlaceInfo memory marketPlaceInfo,
            MarketPlaceStatus status
        ) = getOfferInfo(stockInfo.preOffer);

        // SNIP...

        uint256 settledPointTokenAmount = marketPlaceInfo.tokenPerPoint *
            _settledPoints;
        ITokenManager tokenManager = tadleFactory.getTokenManager();
        if (settledPointTokenAmount > 0) {
            tokenManager.tillIn(
                _msgSender(),
                marketPlaceInfo.tokenAddress,
                settledPointTokenAmount,
                true
            );

            tokenManager.addTokenBalance(
                TokenBalanceType.PointToken,
                offerInfo.authority,
                marketPlaceInfo.tokenAddress,
                settledPointTokenAmount
            );
        }
        // SNIP...
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error that occurs in the settlement function of the DeliveryPlace contract. When a taker calls settleAskTaker to finalize a bid, the contract transfers the promised mockPointToken from the taker and then records the received amount in the userTokenBalanceMap. The code mistakenly passes makerInfo.tokenAddress as the token identifier for the PointToken balance, while the correct identifier should be marketPlaceInfo.tokenAddress, which represents the point token used in the market. This mismatch causes the PointToken balance to be credited under an unrelated token address, leaving the intended point token balance unchanged. The root cause is a copy‑and‑paste or logic mistake where the wrong struct field is used in the call to tokenManager.addTokenBalance. An attacker or any user executing a normal settlement can trigger the bug simply by following the standard workflow: create a bid, a taker creates a matching order, the admin updates the market, and the taker calls settleAskTaker. Because the function does not validate that the token address matches the market’s point token, the incorrect address is accepted and the internal accounting is corrupted. The impact is that the user’s point token balance appears as zero or lower than expected, while the contract’s total accounting shows the tokens were received, leading to potential loss of funds, failed withdrawals, or mismatched accounting reports. This condition appears only during the settlement step and only affects participants who settle asks, but it can affect the entire protocol if many settlements are processed incorrectly. The issue was discovered during a manual audit and reproduced with a test that logs the userTokenBalanceMap after settlement, showing a zero balance for the point token and an unexpected balance under the maker’s token address. The bug is subtle because the external transfer succeeds and no revert occurs; the UI may still show a successful transaction, while the internal balance is wrong, making it hard to notice without inspecting the mapping directly. To fix the problem, the contract should replace makerInfo.tokenAddress with marketPlaceInfo.tokenAddress in the addTokenBalance call, ensuring that the PointToken balance is recorded under the correct token address and that the accounting invariants of the market are preserved.
