---
id: 20921
severity: "High"
---

# Partially filled Short Records created without a short order cannot be liquidated and exited

## Description

When a Short Order is being created it tries to fill its Short Record. If it fills the Short Record, the Short Record is given a filled status (`SR.FullyFilled`) and the Short Order isn’t added to the market. But if it doesn’t fill the Short Record, it is given a partially filled status (`SR.PartiallyFilled`) and the remaining part of the Short Order is added to the market.

The issue is the current implementation doesn’t add the Short Order to the market every time the Short Record is partially filled. It does this in the `sellMatchAlgo()` function loop when it tries to match bids.
```solidity
matchIncomingSell(asset, incomingAsk, matchTotal);
if (incomingAsk.ercAmount.mul(incomingAsk.price) >= minAskEth) {
    addSellOrder(incomingAsk, asset, orderHintArray);
}
s.bids[asset][C.HEAD].nextId = C.TAIL;
return;
```
When the Short Order is being matched in the `sellMatchAlgo()` loop, it encounters the check in the `if` statement above. If the value of the erc remaining in the short is less than `minAskEth` it is not added to the market. The Short Record is already given the `SR.PartiallyFilled` status before the check.

When this happens, the Short Record is created with no associated Short Order. This prevents the user from exiting the Short Record and a liquidator from liquidating the position if it ever becomes liquidatable. These actions revert with `InvalidShortOrder()` error in the following portion of the code.

## Proof of Concept

The tests can be run in the `Shorts.t.sol` file.

The POC below consists of 5 tests:

* `test_FailExit()`: Shows how exiting a Short Record can fail.
* `test_CreateShortLessThanMin()`: Shows how a Short Record with less erc debt than the minimum can be created.
* `test_FailPrimaryLiquidation()`: Shows how primary liquidation fails.
* `test_FailSecondaryLiquidation()`: Shows how Secondary liquidation fails.
* `test_PassSecondaryLiquidation()`: Shows how Secondary Liquidation can pass and exposes another bug.

It also contains a utility function for setting up the Short Record, `createPartiallyFilledSR`.

Add this import statement to the top of the `Shorts.t.sol` file:
```solidity
import {STypes, MTypes, O, SR} from "contracts/libraries/DataTypes.sol";
```
```solidity
// util function and errors used by test
error InvalidShortOrder();
error SecondaryLiquidationNoValidShorts();
function createPartiallyFilledSR(uint amount) public 
  returns (STypes.ShortRecord memory short)
{
    // get minimum ask
    uint minAskEth = diamond.getAssetNormalizedStruct(asset).minAskEth;

    // The bid is opened with an amount that allows short to be 1 less than
    // the minAskEth.
    fundLimitBidOpt(1 ether, uint88(amount - minAskEth + 1), receiver);
    // open short
    fundLimitShortOpt(1 ether,uint88(amount), sender);
    // get the ShortRecord created
    short = getShortRecord(sender, C.SHORT_STARTING_ID);
    assertTrue(short.status == SR.PartialFill);

    // no short orders
    STypes.Order[] memory shortOrders = getShorts();
    assertEq(shortOrders.length, 0);

    return short;
}

function test_FailExit() public {
    // create partially filled SR with no short order
    createPartiallyFilledSR(3000 ether);
    // give sender assets to exit short
    deal(asset, sender, 1000 ether);
    // cannot exit the SR
    vm.expectRevert(InvalidShortOrder.selector);
    exitShortWallet(C.SHORT_STARTING_ID, 1000 ether, sender);
}

function test_CreateShortLessThanMin() public {
    // create partially filled SR with no short order
    STypes.ShortRecord memory short = createPartiallyFilledSR(2000 ether);
    uint minShortErc = diamond.getAssetNormalizedStruct(asset).minShortErc;
    // created SR has less than minShortErc 
    assertGt(minShortErc, short.ercDebt);
}

function test_FailPrimaryLiquidation() public {
    // create partially filled SR with no short order
    createPartiallyFilledSR(3000 ether);

    // change price to let short record be liquidatable
    uint256 newPrice = 1.5 ether;
    skip(15 minutes);
    ethAggregator.setRoundData(
        92233720368547778907 wei, int(newPrice.inv()) / ORACLE_DECIMALS, block.timestamp, block.timestamp, 92233720368547778907 wei
    );
    fundLimitAskOpt(1.5 ether, 2000 ether, receiver); // add ask to allow liquidation have a sell
    // liquidation reverts 
    vm.expectRevert(InvalidShortOrder.selector);
    diamond.liquidate(asset, sender, C.SHORT_STARTING_ID, shortHintArrayStorage, 0);
}

function test_FailSecondaryLiquidation() public {
    // create partially filled SR with no short order
    STypes.ShortRecord memory short = createPartiallyFilledSR(3000 ether);
    // change price to let short record be liquidatable
    uint256 newPrice = 1.5 ether;
    skip(15 minutes);
    ethAggregator.setRoundData(
        92233720368547778907 wei, int(newPrice.inv()) / ORACLE_DECIMALS, block.timestamp, block.timestamp, 92233720368547778907 wei
    );

    // give receiver assets to complete liquidation
    deal(asset, receiver, short.ercDebt);
    // create batch
    MTypes.BatchLiquidation[] memory batch = new MTypes.BatchLiquidation[](1);
    batch[0] = MTypes.BatchLiquidation(sender, C.SHORT_STARTING_ID, 0);
    vm.prank(receiver);
    // cannot liquidate
    vm.expectRevert(SecondaryLiquidationNoValidShorts.selector);
    diamond.liquidateSecondary(asset, batch, short.ercDebt, true); 
}

// This shows that secondary liquidation can still occur
function test_PassSecondaryLiquidation() public {
    // create partially filled SR with no short order
    STypes.ShortRecord memory short = createPartiallyFilledSR(3000 ether);
    // change price to let short record be liquidatable
    uint256 newPrice = 1.5 ether;
    skip(15 minutes);
    ethAggregator.setRoundData(
        92233720368547778907 wei, int(newPrice.inv()) / ORACLE_DECIMALS, block.timestamp, block.timestamp, 92233720368547778907 wei
    );

    // create another short for sender
    // the id of this short can be used for liquidation
    fundLimitShortOpt(1 ether, 3000 ether, sender);
    STypes.Order[] memory shortOrders = getShorts();
    shortOrders = getShorts();

    // give receiver assets to complete liquidation
    deal(asset, receiver, short.ercDebt);
    // create batch
    MTypes.BatchLiquidation[] memory batch = new MTypes.BatchLiquidation[](1);
    batch[0] = MTypes.BatchLiquidation(sender, C.SHORT_STARTING_ID, shortOrders[0].id);
    vm.prank(receiver);
    // successful liquidation
    diamond.liquidateSecondary(asset, batch, short.ercDebt, true); 
}
```

## Recommendation

Consider setting `ercAmount` of the `incomingAsk` to zero in the `sellMatchAlgo()` function. This will allow the `matchIncomingSell()` call to set the Short Record to a Fully Filled state.
```diff
                        if (startingId == C.TAIL) {
-                        matchIncomingSell(asset, incomingAsk, matchTotal);

                            if (incomingAsk.ercAmount.mul(incomingAsk.price) >= minAskEth) {
                                addSellOrder(incomingAsk, asset, orderHintArray);
                            }
+                       incomingAsk.ercAmount = 0;
+                       matchIncomingSell(asset, incomingAsk, matchTotal);
                        s.bids[asset][C.HEAD].nextId = C.TAIL;
                        return;
                    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the market engine handles a short position that is only partially filled. When a user opens a short order, the contract attempts to match the order against existing bids. If the match succeeds for the entire amount, the short record is marked as fully filled and the order is stored in the market. However, when the match only covers part of the requested amount, the short record is marked with a partially‑filled status but the remaining portion of the short order is added to the market only if the residual ERC amount multiplied by the price meets the protocol‑defined minimum ask threshold (minAskEth). The implementation checks this condition inside the sellMatchAlgo loop and, if the residual value is below the threshold, it skips the addSellOrder call. Because the short record has already been labelled as partially filled, the short order never gets recorded in the market. The result is an orphaned short record that has no associated order identifier. Any subsequent attempt to exit the short (for example by calling exitShortWallet) or to liquidate it (through primary or secondary liquidation functions) triggers a revert with the InvalidShortOrder error because the contract cannot locate a matching order. This bug manifests only when the remaining ERC debt after a partial fill is smaller than minAskEth, a situation that can arise naturally when market depth is low or when the user submits a short amount that is only marginally larger than the minimum. Users experience the symptom of being unable to close their position: a transaction that should return collateral simply fails, leaving their balance unchanged and the position appearing stuck. Liquidators are similarly blocked, preventing the protocol from enforcing margin requirements and potentially exposing the system to under‑collateralised risk. The issue was uncovered by a suite of unit tests that deliberately created a partially filled short record with a residual amount below the minimum and observed the InvalidShortOrder reverts on exit and liquidation attempts. The bug is subtle because the short record’s status suggests that a position exists and is partially filled, yet the market data structures contain no order, making the problem invisible in normal UI views until an action is taken. Conceptually, the flaw belongs to the class of “orphaned position” or “partial‑fill lifecycle” bugs where state transitions are not kept in sync with order book entries. To remediate the problem the contract should ensure that a short record never ends up in a partially‑filled state without a corresponding order. One practical fix is to force the incoming ask’s ercAmount to zero before invoking matchIncomingSell, which guarantees that the short record will be marked as fully filled and the order lifecycle will be completed. Alternatively, the addSellOrder call could be performed unconditionally or the minimum‑ask check could be adjusted to still create a placeholder order for the residual amount, thereby preserving the invariant that every short record has an associated order that can be exited or liquidated.
