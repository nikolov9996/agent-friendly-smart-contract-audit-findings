---
id: 15819
severity: "High"
---

# listOffer maker can settle offer via settleAskMaker() in Turbo settle type.

## Description

In turbo settle type, the maker is the only person who deposit some collaterals. So the maker should be the only person who can settle ask maker and get back the collateral. But now the listOffer's owner can trigger settleAskMaker() to settle and get back some collateral. This will lead that the maker cannot get back all collaterals.

In Turbo settle type, the maker will add some collateral to create one ask offer. Traders can bid this offer to buy some points. And these takers can resell their points bought from the maker via listOffer() with 0 collateral because of the turbo mode.
When the market's status is changed to asksettle, the maker will settle this to get back the collateral via settleAskMaker(). All takers who still hold some points can get the point token via closeBidTaker().
The problem exists in settleAskMaker(). One resell offer(via listOffer())'s owner can still settle this offer to get some collateral via settleAskMaker() in turbo mode. And these collateral belongs to the maker, the original offer owner. This will lead the maker lose some collateral.

One possible attack vector:
Alice creates one ask offer as the maker, deposit 10000 collateral token to sell 1000 points.
Bob creates one taker to buy 500 points via Alice's offer.
Bob resell his points via listOffer().
Cathy create one taker to match the bob's offer.
MarketPlace's status is changes to asksettle.
Bob call settleAskMaker() to settle his offer to get some collaterals. Bob withdraws the collateral from the TokenManager.
Alice calls settleAskMaker() to settle her offer to get back all collaterals. Although the account's balance is updated in userTokenBalanceMap. But maybe there is not enough collateral token in capitalPool to withdraw.
```solidity
    function settleAskMaker(address offer, uint256 settledPoints) external {
        (
            OfferInfo memory offerInfo,
            MakerInfo memory makerInfo,
            MarketPlaceInfo memory marketPlaceInfo,
            MarketPlaceStatus status
        ) = getOfferInfo(_offer);
        // The maker has already selled usedPoints.
        if (_settledPoints > offerInfo.usedPoints) {
            revert InvalidPoints();
        }
        // fixedratio does not support settle in this contract.
        if (marketPlaceInfo.fixedratio) {
            revert FixedRatioUnsupported();
        }
        // 
        if (offerInfo.offerType == OfferType.Bid) {
            revert InvalidOfferType(OfferType.Ask, OfferType.Bid);
        }

        if (
            offerInfo.offerStatus != OfferStatus.Virgin &&
            offerInfo.offerStatus != OfferStatus.Canceled
        ) {
            revert InvalidOfferStatus();
        }

        if (status == MarketPlaceStatus.AskSettling) {
            if (_msgSender() != offerInfo.authority) {
                revert Errors.Unauthorized();
            }
        } else {
            if (_msgSender() != owner()) {
                revert Errors.Unauthorized();
            }
            if (_settledPoints > 0) {
                revert InvalidPoints();
            }
        }
        // Calculate the token amount
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
        }

        uint256 makerRefundAmount;
        // The maker can receive their collateral if they pay enough point token.
        if (_settledPoints == offerInfo.usedPoints) {
            if (offerInfo.offerStatus == OfferStatus.Virgin) {
                makerRefundAmount = OfferLibraries.getDepositAmount(
                    offerInfo.offerType,
                    offerInfo.collateralRate,
                    offerInfo.amount,
                    true,
                    Math.Rounding.Floor
                );
            } else {
                uint256 usedAmount = offerInfo.amount.mulDiv(
                    offerInfo.usedPoints,
                    offerInfo.points,
                    Math.Rounding.Floor
                );

                makerRefundAmount = OfferLibraries.getDepositAmount(
                    offerInfo.offerType,
                    offerInfo.collateralRate,
                    usedAmount,
                    true,
                    Math.Rounding.Floor
                );
            }

            tokenManager.addTokenBalance(
                // @audit-fp [L] improper balance type
                TokenBalanceType.SalesRevenue,
                _msgSender(),
                makerInfo.tokenAddress,
                makerRefundAmount
            );
        }

        IPerMarkets perMarkets = tadleFactory.getPerMarkets();
        perMarkets.settledAskOffer(
            _offer,
            _settledPoints,
            settledPointTokenAmount
        );
......
    }
```

## Proof of Concept

In below test case, user2 is not the maker, users buy points and resell points. When the markerplace's status is changed to the asksettle status, users can settle his offer to get back some collaterals.
```solidity
    function testPocsettleaskoffer() public {
        vm.startPrank(user);
        
        preMarktes.createOffer(
            CreateOfferParams(
                marketPlace,
                address(mockUSDCToken),
                1000,
                0.01 * 1e18,
                12000,
                300,
                OfferType.Ask,
                OfferSettleType.Turbo
            )
        );
        vm.stopPrank();
        vm.startPrank(user2);
        address offerAddr = GenerateAddress.generateOfferAddress(0);
        preMarktes.createTaker(offerAddr, 500);

        address stock1Addr = GenerateAddress.generateStockAddress(1);
        preMarktes.listOffer(stock1Addr, 0.006 * 1e18, 12000);
        address offer1Addr = GenerateAddress.generateOfferAddress(1);
        //preMarktes.closeOffer(stock1Addr, offer1Addr);
        //preMarktes.relistOffer(stock1Addr, offer1Addr);

        vm.stopPrank();

        vm.startPrank(user1);
        preMarktes.createTaker(offer1Addr, 500);
        systemConfig.updateMarket(
            "Backpack",
            address(mockPointToken),
            0.01 * 1e18,
            block.timestamp - 1,
            3600
        );
        vm.stopPrank();
        vm.startPrank(user2);
        mockPointToken.approve(address(tokenManager), 10000 * 10 * 18);
        deliveryPlace.settleAskMaker(offer1Addr, 500);
        vm.stopPrank();
        vm.startPrank(user);
        mockPointToken.approve(address(tokenManager), 10000 * 10 * 18);
        deliveryPlace.settleAskMaker(offerAddr, 500);
        vm.stopPrank();
    }
```

## Recommendation

In turbo mode, only the maker or the original offer's owner can trigger settleAskMaker()

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability occurs in the Turbo settlement mode of a marketplace contract where the function settleAskMaker is intended to allow only the original maker of an ask offer to retrieve the collateral that was locked when the offer was created. In Turbo mode the maker deposits collateral and subsequent takers can buy points and resell them through listOffer without posting additional collateral. When the market transitions to the AskSettling state, the contract checks the caller against the authority field of the offer being settled. Because a resell offer created via listOffer stores the reseller as its authority, the contract mistakenly permits that reseller to invoke settleAskMaker on the resell offer and claim a portion of the original maker’s collateral. The root cause is an insufficient authorization check that does not distinguish between the primary ask offer and secondary resale offers, allowing any owner of a listed resale to settle and withdraw collateral that legally belongs to the original maker. An attacker can exploit this by creating an ask offer, having a taker purchase points, reselling those points, and then, once the marketplace status changes to AskSettling, calling settleAskMaker on the resale offer to withdraw collateral. The impact is that the original maker receives less collateral than expected, effectively causing funds to disappear from the maker’s balance and breaking the accounting assumptions of the protocol. This situation arises only when the Turbo settle type is used, the market is in AskSettling, and there exist resale offers listed by third parties. The affected parties include the original maker, any reseller who can improperly claim collateral, and the overall protocol which may suffer loss of trust and financial imbalance. The issue was discovered during a security audit when a test case demonstrated that a non‑maker user could successfully call settleAskMaker and receive collateral. The bug is subtle because the function appears to validate offer status and marketplace status correctly, masking the deeper logical flaw in the authority check. To remediate, the contract should enforce that settleAskMaker can be called only by the original maker of the primary ask offer or by the contract owner, and it should explicitly reject calls on resale offers. Adding a check that the offer being settled is the original ask (e.g., verifying a flag or comparing the maker address) and ensuring the collateral pool has sufficient balance before refunding will close the loophole and restore correct financial behavior.
