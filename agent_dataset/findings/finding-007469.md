---
id: 7469
severity: "High"
---

# User's can loose collateral when exiting a short

## Description

In exitShort, the ShortRecord is exited by placing a bid on the orderbook. If a partially filled ShortRecord matches with its own associated short order and fully buys back the debt, the user will loose the collateral present in the short order.

If the user's own short order is matched when calling exitShort, the debt and collateral of the short order is added to the same ShortRecord that is being exited. If the user wanted to buyBack the entire debt and is successful in doing so, the ShortRecord will be deleted.
```solidity
    function exitShort(
        address asset,
        uint8 id,
        uint88 buyBackAmount,
        uint80 price,
        uint16[] memory shortHintArray
    )
        external
        isNotFrozen(asset)
        nonReentrant
        onlyValidShortRecord(asset, msg.sender, id)
    {
        
       // more code

        // Create bid with current msg.sender
        (e.ethFilled, e.ercAmountLeft) = IDiamond(payable(address(this))).createForcedBid(
            msg.sender, e.asset, price, buyBackAmount, shortHintArray
        );

        e.ercFilled = buyBackAmount - e.ercAmountLeft;
        Asset.ercDebt -= e.ercFilled;
        s.assetUser[e.asset][msg.sender].ercEscrowed -= e.ercFilled;

        // @audit if the debt is fully filled, the short record is deleted
        // Refund the rest of the collateral if ercDebt is fully paid back
        if (e.ercDebt == e.ercFilled) {
            // Full Exit
            LibShortRecord.disburseCollateral(
                e.asset, msg.sender, e.collateral, short.zethYieldRate, short.updatedAt
            );
            LibShortRecord.deleteShortRecord(e.asset, msg.sender, id); // prevent re-entrancy
```
https://github.com/Cyfrin/2023-09-ditto/blob/a93b4276420a092913f43169a353a6198d3c21b9/contracts/facets/ExitShortFacet.sol#L145-L224

Since the user's newly added collateral from the partially filled short order is accounted in this ShortRecord, it will lead to the user loosing the collateral.
```solidity
    function matchlowestSell(
        address asset,
        STypes.Order memory lowestSell,
        STypes.Order memory incomingBid,
        MTypes.Match memory matchTotal
    ) private {

            // more code

            // @audit if the short order is already associated with a shortRecord, the collateral and debt is accounted there
            if (lowestSell.shortRecordId > 0) {
                // shortRecord has been partially filled before
                LibShortRecord.fillShortRecord(
                    asset,
                    lowestSell.addr,
                    lowestSell.shortRecordId,
                    status,
                    shortFillEth,
                    fillErc,
                    matchTotal.ercDebtRate,
                    matchTotal.zethYieldRate
                );
```
https://github.com/Cyfrin/2023-09-ditto/blob/a93b4276420a092913f43169a353a6198d3c21b9/contracts/facets/BidOrdersFacet.sol#L254-L294

Example scenario:
User calls the createLimitShort function with price = 2000 and debt = 100. Hence supplying collateral = 5 * 2000 * 100
Based on the current bids present in the orderbook, 50 ercTokens is sold. 
This will create a ShortRecord with debt = 50 and collateral = 3 * 2000 * 100 and a short order will be placed on the orderbook with ercTokens amount = 50 and price = 2000.
After some time the user decides to completely exit the short. The user calls exitShort() with buyBackAmount = 50 and price = 2000.
The lowest priced short order happens to be that of the user itself. Hence these two are matched resulting in the short order accounting for the new collateral and debt in the same ShortRecord.
ShortRecord.debt += 50 and ShortRecord.collateral += 3 * 2000 * 100.
Since the enitre bid order is filled, e.ercDebt == e.ercFilled will pass, executing LibShortRecord.deleteShortRecord(e.asset, msg.sender, id). This will delete the ShortRecord leading to the user not being able to claim his newly added debt and collateral. 

POC Test
Add the following changes to test/Shorts.t.sol and run.
```diff
diff --git a/test/Shorts.t.sol b/test/Shorts.t.sol
index f1c3927..79c4d52 100644
--- a/test/Shorts.t.sol
+++ b/test/Shorts.t.sol
@@ -72,6 +72,51 @@ contract ShortsTest is OBFixture {
         );
     }
function test_userLoosesCollateralOnMatchingWithUsersOwnShort() public{
uint88 DEFAULTAMOUNTHALF = DEFAULT_AMOUNT/2;
//funded inside fundLimitShortOpt
uint88 userVaultEthEscrowedInitial = SHORT1PRICE.mulU80(DEFAULTAMOUNT) * 5;
//bids fills half the short
fundLimitBidOpt(SHORT1PRICE, DEFAULTAMOUNT_HALF, receiver);
fundLimitShortOpt(SHORT1PRICE, DEFAULTAMOUNT, sender);
//after short creation funds are split for the short order and the collateral
assertEq(diamond.getVaultUserStruct(vault,sender).ethEscrowed,userVaultEthEscrowedInitial - SHORT1PRICE.mulU80(DEFAULTAMOUNT) * 5);
STypes.Order memory userShortOrder = diamond.getShorts(asset)[0];
assertEq(userShortOrder.addr,sender);
assertEq(userShortOrder.ercAmount,DEFAULTAMOUNTHALF);
STypes.ShortRecord memory userShortRecord = diamond.getShortRecords(asset,sender)[0];
assertEq(
userShortRecord.ercDebt, DEFAULTAMOUNTHALF
);
assertEq(
userShortRecord.collateral,
SHORT1PRICE.mulU80(DEFAULTAMOUNT_HALF) * 6
);
//exit matching with the same short. this is supposed to move the funds from the short order to the short record. it does but since the record gets cancelled the user can no longer access these funds
vm.prank(sender);
uint16[] memory shortHintArray = new uint16[](1);
shortHintArray[0] = userShortOrder.id;
diamond.exitShort(asset,userShortRecord.id,userShortRecord.ercDebt,SHORT1_PRICE,shortHintArray);
//short order gets filled and short record gets cancelled
assertEq(diamond.getShorts(asset).length,0);
assertEq(diamond.getShortRecords(asset,sender).length,0);
// user now only has half of initial
assertEq(diamond.getVaultUserStruct(vault,sender).ethEscrowed,userVaultEthEscrowedInitial/2);
}
function prepareExitShort(uint8 exitType) public {
         makeShorts();
```

Users will loose collateral

## Proof of Concept

Add the following changes to test/Shorts.t.sol and run.
```diff
diff --git a/test/Shorts.t.sol b/test/Shorts.t.sol
index f1c3927..79c4d52 100644
--- a/test/Shorts.t.sol
+++ b/test/Shorts.t.sol
@@ -72,6 +72,51 @@ contract ShortsTest is OBFixture {
         );
     }
function test_userLoosesCollateralOnMatchingWithUsersOwnShort() public{
uint88 DEFAULTAMOUNTHALF = DEFAULT_AMOUNT/2;
//funded inside fundLimitShortOpt
uint88 userVaultEthEscrowedInitial = SHORT1PRICE.mulU80(DEFAULTAMOUNT) * 5;
//bids fills half the short
fundLimitBidOpt(SHORT1PRICE, DEFAULTAMOUNT_HALF, receiver);
fundLimitShortOpt(SHORT1PRICE, DEFAULTAMOUNT, sender);
//after short creation funds are split for the short order and the collateral
assertEq(diamond.getVaultUserStruct(vault,sender).ethEscrowed,userVaultEthEscrowedInitial - SHORT1PRICE.mulU80(DEFAULTAMOUNT) * 5);
STypes.Order memory userShortOrder = diamond.getShorts(asset)[0];
assertEq(userShortOrder.addr,sender);
assertEq(userShortOrder.ercAmount,DEFAULTAMOUNTHALF);
STypes.ShortRecord memory userShortRecord = diamond.getShortRecords(asset,sender)[0];
assertEq(
userShortRecord.ercDebt, DEFAULTAMOUNTHALF
);
assertEq(
userShortRecord.collateral,
SHORT1PRICE.mulU80(DEFAULTAMOUNT_HALF) * 6
);
//exit matching with the same short. this is supposed to move the funds from the short order to the short record. it does but since the record gets cancelled the user can no longer access these funds
vm.prank(sender);
uint16[] memory shortHintArray = new uint16[](1);
shortHintArray[0] = userShortOrder.id;
diamond.exitShort(asset,userShortRecord.id,userShortRecord.ercDebt,SHORT1_PRICE,shortHintArray);
//short order gets filled and short record gets cancelled
assertEq(diamond.getShorts(asset).length,0);
assertEq(diamond.getShortRecords(asset,sender).length,0);
// user now only has half of initial
assertEq(diamond.getVaultUserStruct(vault,sender).ethEscrowed,userVaultEthEscrowedInitial/2);
}
function prepareExitShort(uint8 exitType) public {
         makeShorts();
```

## Recommendation

```diff
diff --git a/contracts/facets/ExitShortFacet.sol b/contracts/facets/ExitShortFacet.sol
index 8c73c38..4dadd69 100644
--- a/contracts/facets/ExitShortFacet.sol
+++ b/contracts/facets/ExitShortFacet.sol
@@ -216,7 +216,7 @@ contract ExitShortFacet is Modifiers {
         s.assetUser[e.asset][msg.sender].ercEscrowed -= e.ercFilled;
 
         // Refund the rest of the collateral if ercDebt is fully paid back
-        if (e.ercDebt == e.ercFilled) {
+        if (e.ercDebt == e.ercFilled && short.ercDebt == e.ercDebt) {
             // Full Exit
             LibShortRecord.disburseCollateral(
                 e.asset, msg.sender, e.collateral, short.zethYieldRate, short.updatedAt
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting and state‑cleanup flaw that can cause a user to lose the collateral that backs a short position when they try to exit that short. The root cause lies in the exitShort logic, which deletes a ShortRecord as soon as the debt reported in the exit call (e.ercDebt) equals the amount of debt that was actually filled (e.ercFilled). When the user’s own short order happens to be the cheapest order on the book, the forced bid created by exitShort matches against that same order. The matching routine adds the newly bought‑back debt and the associated collateral to the existing ShortRecord before the deletion check runs. Because the check only compares e.ercDebt and e.ercFilled, it does not verify that the ShortRecord’s original debt (short.ercDebt) has been fully repaid. Consequently the ShortRecord is removed while it still holds the freshly added collateral, making that collateral unrecoverable. An attacker – or even an honest user – can trigger the condition simply by exiting a short when their own order is the best match, which is a realistic scenario in a decentralized order‑book environment. The impact is that the user’s escrowed ETH (or other collateral) is reduced unexpectedly; from the UI the user sees a partial refund or a balance that is lower than expected, often described as “funds disappear” or “collateral missing”. The bug affects any participant who opens a short and later exits it, and it also undermines the protocol’s accounting guarantees because the total collateral accounting no longer matches the recorded debt. The issue was discovered during a manual audit and reproduced with a targeted unit test that showed the ShortRecord being deleted and the user ending up with only half of the original escrowed amount. It is hard to notice because the transaction completes without reverting, the debt appears to be fully repaid, and the missing collateral is not emitted in an event. The proper fix is to ensure that the ShortRecord is only deleted when the original short’s debt is fully repaid and no new collateral has been added, for example by adding a condition that short.ercDebt == e.ercDebt before calling deleteShortRecord, or by preventing a short from matching against its own order during exit. This change prevents the accidental loss of collateral and restores the intended accounting behavior where a full exit returns all collateral to the user.
