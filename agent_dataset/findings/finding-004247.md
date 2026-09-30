---
id: 4247
severity: "High"
---

# Allowing the creation of "dust CDPs" could lead redeemers/liquidators to be not profitable or not wanting to perform the operation

## Description

When collateral.getPooledEthByShares(DECIMAL_PRECISION) < DECIMAL_PRECISION both the BorrowerOperations._adjustCdpInternal and LiquidationLibrary._liquidateCDPPartially allow the collateral balance of the CDP to go below the constant MIN_NET_COLL value of 2 stETH. This allows the possibility (voluntarily or involuntarily) to generate (by adjusting or partially liquidating CDPs) "dust CDPs" where the collateral and debt amount of the CDP is very low (dust level). When those "dust CDPs" exists inside the protocol, the following scenarios could happen:

• Redeemers (that, unlike liquidators, will not get the LIQUIDATOR_REWARD and can't directly choose the CDPs from which they want to redeem from) could incur in loss (collateral receives is less valuable than the gas cost of the operation) or simply decide that the operation is not worth the gas cost.

• Liquidators, depending on stETH share value and gas cost, could incur in a loss or simply decide that the operation is not worth.

Let's review how it's possible to create such "dust CDPs" and why redemptions and liquidations operations could not be profitable.

Create "dust CDP" by leveraging BorrowerOperations._adjustCdpInternal

In this scenario, the user/attacker creates a "dust CDP" by using adjusting the CDP coll/debt via the BorrowerOperations._adjustCdpInternal operation.

Let's set up an initial scenario just to showcase the test:

• 1 BTC = 15 stETH <> 1 stETH = ~0.066666666 BTC.

• 1 stETH = 1 ETH.

• 1 stETH share = 1 stETH.

1) The protocol has some whale CDP opened with coll/debt ratio very high, this allows us to have TCR >> CCR just to be sure that we are in "normal mode" and that the next events do not trigger the "recovery mode".

2) Alice creates a CDP with a coll/debt ratio equal to ~MMCR. In our example, she creates a CDP with:

1) collateral = 10 stETH (that is equal to 10 ether of stETH shares).

2) debt = 0.606060606060606054 ether of eBTC.

3) Lido validators get slashed/incur penalties and 1 stETH shares = 1 stETH - 1 wei. The share value has decreased of just 1 wei.

4) At this point Alice would be liquidable, but it is not relevant because she promptly performs the following action:

1) She repays most of her debt, leaving only 0.0000001 ether of debt in her CDP. This was just an example number, she could go further down as much as she wants.

2) She withdraws as much of collateral as possible. The amount of collateral she can withdraw depends mostly on the debt she still has in her CDP because at the end of the operation the ICR must always be > MCR.

At the end of the scenario setup, Alice's CDP will be as follows:

• coll = 0.000001650000000002 of stETH shares.

• debt = 0.0000001 of eBTC.

• ICR = 1100000000000666655 that is still ~> MCR.

• Her CDP is not liquidable at this time.

Note that it is also possible to create "dust CDPs" by executing a partial liquidation.

Consequences on Redemption

When user call CdpManager.redeemCollateral they specify the amount of eBTC that they want to redeem for collateral. The execution will iterate over all the CDPs that are not liquidable starting from the CDP with lower ICR but still ICR >= MCR.

For each CDP, the redeemer will receive an amount of collateral (in stETH shares) equal to collateral.getSharesByPooledEth( (singleRedemption.eBtcToRedeem * DECIMAL_PRECISION ) / _redeemColFromCdp._price ).

The redemption of the CDP can be full (CDP is closed) or partial, depending on the CDP.debt and the amount of remaining eBTC provided to redeem from the protocol.

Note 1: As opposed to a liquidation operation, the redeemer will not receive the gas stipend and will need to pay a fee on top of the collateral received (min 0.5%, max 100%). Note 2: As opposed to a liquidation operation, the redeemer cannot specify which CDPs they want to redeem from, they will always redeem from the CDP with lower ICR that is still above MCR.

If the amount of stETH shares received by the redeemer is less than the gas spent to execute the redeem operation, there are two consequences:

1) The redeemer will lose money on the operation.

2) The redeemer won't perform the operation because it will lose money. The redeem operation is part of the soft-peg system of eBTC.

Can the redeem operation not be profitable?

@GalloDaSballo stated that the redeemCollateral operation should cost:

• 138k gas units on avg.

• 256k gas units on max.

Let's assume the user calls CdpManager.redeemCollateral with an amount of eBTC enough just to redeem from the first available CDP to be redeemed from (we can generalize that more or less the cost to redeem fully 100 CDPs is equal to the same amount multiplied by 100).

The operation would cost:

• avg gas used 138k, 150 gwei gas cost ≈ 0.0207 ETH.

• max gas used 256k, 150 gwei gas cost ≈ 0.0384 ETH.

• avg gas used 138k, 300 gwei gas cost ≈ 0.0414 ETH.

• max gas used 256k, 300 gwei gas cost ≈ 0.0768 ETH.

Let's assume that:

• 1 BTC = 15 stETH <> 1 stETH = ~0.066666666 BTC.

• 1 stETH = 1 ETH.

• stETH share drops to 1 ether - 1 wei just to simulate the scenario.

• assume that Badger does not have a fee on redemption (just to simplify things). The fee would just make the situation for the redeemer worst, if we are not profitable without the fee, we would not be profitable with the fee as well.

Let's use the data from the first scenario where to perform the operation we will use 138k gas and that gas costs ~150 gwei.

To be profitable (and probably it's not enough because after the redemption you want to do something with those shares like swapping them, repaying a flashloan and so on) the amount of stETH shares that you need to receive must be greater than 0.0207 ETH.

This means that collateral.getSharesByPooledEth(cdp.debt * DECIMAL_PRECISION / price) ≈ collateral.getSharesByPooledEth(cdp.debt * 1 ether / ~0.066666666 ether) must be >= ~0.0207 ETH of stETH shares.

Just to simply things, let's assume that Badger does not take a cut on that collateral (as we said, it takes a fee that goes from a min of 0.5% to 100%).

To be profitable (collateral received is greater than gas spent) the redeemer should need to receive at least 0.0207 ETH so it would have to be able to redeem at least 0.0207 * 0.066666666 BTC of debt = 0.00138 BTC.

Is it possible to adjust a CDP in a way that:

• ICR is very near MCR (not liquidable, but will be selected first when redemptions happen).

• Very low (dust level) amount of debt.

In the setup of the scenario, we have shown (and demonstrated in the foundry test at the very end) that it is possible to generate a "dust CDP" by executing adjusting the CDP balance. In the example, Alice was able to bring down the debt (and withdraw as much collateral as possible) to 0.0000001 of eBTC (note that she could have reduced even more the debt, aggravating the "dust level" of the CDP).

The result will be that the redeemer will pay (when gas is at ~150 gwei) ~0.0207 ETH to redeem 0.0000001 ether of eBTC for 0.000001492499981999 ether of stETH shares.

Consequences on Liquidation

The liquidation process is less affected by the "dust CDP" situation for different reason, but it can anyway lead to situations where:

• The liquidator does not yield any profit from the liquidation (neutral result or loss of funds because of gas cost).

• The liquidator does not execute liquidation at all because there would be no profit (this is bad for the protocol).

The Liquidation scenario is less affected because:

1) Liquidator does get a GAS STIPEND of 0.2 stETH by fully liquidating the CDP. This GAS STIPEND is not rewarded if the liquidator performs a partial liquidation, and at this point we return to a situation similar to the redemption one.

2) Liquidators can choose which CDP they want to liquidate by specifying a single CDP or an array of CDPs.

Can the liquidation operation not be profitable?

Because the "dust CDP" has a tiny amount of collateral, it's safe to assume that the premium that the liquidator gets back from the liquidation process will not influence in the overall profitability of the operation.

We can state that the operation is not profitable when the GAS STIPEND is not enough to cover the gas cost of the transaction. This is influenced by two factors:

1) The real value of the GAS STIPEND. When a user opens a CDP, he needs to "pay" an additional GAS STIPEND that is equal to 0.2 stETH. Those 0.2 stETH are converted to stETH shares when the CDP is opened. The real value of those shares could end up not being 0.2 stETH when it's returned to the liquidator because it depends on the current (at liquidation time) value of those shares. If the value has decreased (because of slashing/penalties on Lido) compared to the value at the time of the creation of the CDP (involved in the liquidation process) the liquidator will receive less than 0.2 stETH. We also need to take in consideration that stETH is not always perfectly pegged to ETH and there have been cases where stETH was worth less than ETH (~7% less).

2) Gas price. Another factor to take in consideration is the gas price to execute the "direct" liquidation or the "MEV" liquidation (that could involve more complex operations like flashloaning, pre/post swaps, transfers and so on).

Liquidation Scenario 1: stETH:BTC price decrease, stETH share value remain the same

In the first scenario, we reduce the stETH:BTC price by a tiny fraction just to make Alice CDP be liquidable.

Alice CDP:

• coll = 0.000001650000000002 shares equal to 0.000001650000000001 of stETH.

• debt = 0.0000001 of eBTC.

After the liquidation, the liquidator has collected 0.20000165 stETH.

In this scenario, the GAS STIPEND rewarded to the liquidator is mostly the same as the one supplied by Alice at the CDP opening (share value has decreased by just 1 wei in the meanwhile). This means that in this very specific case, the profitability of the operation depends on mostly by the gas cost of the execution itself.

From an analysis made by the Badger team, the gas consumption of a "MEV Liquidation" is around 650325 units of gas.

• with gas cost of ~150 gwei the liquidation would cost ~0.1 ETH.

• with gas cost of ~300 gwei the liquidation would cost ~0.2 ETH.

With the gas cost of ~300 gwei we are at the very limit of not being cost neutral, and we are not taking in consideration that the stETH:ETH could not be pegged or that the general value of stETH in the market has decreased.

Liquidation Scenario 2: stETH:BTC remains the same, stETH share value decreases

In this scenario, the stETH share value has decreased because of a slash/penalty event on Lido. 1 stETH share is now worth 0.9 stETH. The price of stETH:BTC remain the same.

Because of the decrease in the share value, we are in this situation:

• Alice CDP liquidatorRewardShares before the slash was worth ~0.2 stETH.

• Alice CDP liquidatorRewardShares after the slash is worth ~0.18 stETH.

At the end of the liquidation process, the liquidator has received ~0.180001485 of stETH (gas stipend + collateral liquidated).

Compared to Scenario 1, in the Scenario 2 the gas price influences even more the profitability of the liquidation operation. If the gas cost to liquidate Alice's CDP is higher than ~0.180001485 stETH the operation will only be a cost for the liquidator.

Test
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.17;
import "forge-std/Test.sol";
import {eBTCBaseInvariants} from "./BaseInvariants.sol";
contract FAdjustDustCDPTest is eBTCBaseInvariants {
    uint256 public constant MCR = 1100000000000000000; // 110%
    uint256 public constant DECIMAL_PRECISION = 1 ether;
    uint256 public constant MIN_COLLAERAL_SIZE = 2 ether;
    uint256 public constant GAS_STIPEND = 0.2 ether;
    address user1;
    address user2;
    bytes32 cdp1;
    bytes32 cdp2;

    function setUp() public override {
        super.setUp();
        // current value of the shares on lido (more or less)
        collateral.setEthPerShare(1 ether);
        priceFeedMock.setPrice((1 ether * DECIMAL_PRECISION) / 15 ether);
        connectCoreContracts();
        connectLQTYContractsToCore();
    }

    /// @notice the scope of this funcion is to prepare the test scenario
    /// 1) Warp at least 14 days to enable the redeem operation
    /// 2) Create two users with funds to open CDPs
    /// 3) First user open a CDP as a whale providing a lot of collateral to bring up TCR
    /// 4) Second user open a CDP with ICR ~= MCR
    /// 5) Eth Per Share goes from 1 ether -> 1 ether - 1 wei just to trigger the scenario
    /// 6) Second user adjust it's CDP to create a "dust CDP"
    function _createDustCDPFromAdjust(uint256 finalDustDebt) public {
        vm.warp(block.timestamp + 30 days);
        // let's say that I open a cdp with the minimum amount
        address payable[] memory users;
        users = _utils.createUsers(2);
        user1 = users[0];
        user2 = users[1];
        vm.label(user1, "user_1");
        vm.label(user2, "user_2");
        _dealCollateralAndPrepForUse(user1);
        _dealCollateralAndPrepForUse(user2);
        // let's say that we have a big whale that open a CDP
        // to bring the TCR high
        vm.startPrank(user1);
        uint256 borrowedAmount = _utils.calculateBorrowAmount(
            100 ether,
            priceFeedMock.fetchPrice(),
            COLLATERAL_RATIO
        );
        cdp1 = borrowerOperations.openCdp(borrowedAmount, "hint", "hint", 400 ether + GAS_STIPEND);
        vm.stopPrank();
        // user2 open the CDP just abobe MCR
        vm.startPrank(user2);
        borrowedAmount = _utils.calculateBorrowAmount(
            10 ether,
            priceFeedMock.fetchPrice(),
            MINIMAL_COLLATERAL_RATIO
        );
        cdp2 = borrowerOperations.openCdp(borrowedAmount, "hint", "hint", 10 ether + GAS_STIPEND);
        // share value decrease sub 1 ether
        collateral.setEthPerShare(1 ether - 1);
        // redeem and withdraw the max possible amount
        // how much do we want to leave as debt? the min possible?
        (uint256 cdp2Debt, uint256 cdp2Coll, ) = cdpManager.getEntireDebtAndColl(cdp2);
        uint256 removedDebt = cdp2Debt - finalDustDebt;
        borrowerOperations.repayEBTC(cdp2, removedDebt, "", "");
        (cdp2Debt, cdp2Coll, ) = cdpManager.getEntireDebtAndColl(cdp2);
        uint256 maxWithdrawColl = maxWithdraw(cdp2Coll, cdp2Debt);
        borrowerOperations.withdrawColl(cdp2, maxWithdrawColl, "", "");
        vm.stopPrank();
    }

    function testLiquidationNotProfitable() public {
        _createDustCDPFromAdjust(0.0000001 ether);
        // let's try to just fully liquidate it
        address liquidator = makeAddr("liquidator");
        (uint256 cdp2Debt, uint256 cdp2Coll, ) = cdpManager.getEntireDebtAndColl(cdp2);
        // send to redeemer just what's needed to fully redeem cdp2
        vm.prank(user1);
        eBTCToken.transfer(liquidator, cdp2Debt);
        ////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////
        // SUBSCENARIO 1: oracle price decrease, stETH share value does not decrease anymore
        // In this scenario as long as gas price are lower than 310 gwei the
        // operation should be still neutral/positive from a profit prospective
        // This depends also on the stETH price and peg to ETH
        // The Liquidator receive more or less ONLY the GAS STIPEND of ~0.2 stETH
        ////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////
        uint256 snapshot = vm.snapshot();
        // let's say that the price decrese just to make it liquidable
        priceFeedMock.setPrice(priceFeedMock.fetchPrice() - 0.0000000000001 ether);
        // In this case the liquidator is still profittable just because
        CdpInfo memory cdp2Before = getCdpInfo(cdp2);
        vm.prank(liquidator);
        cdpManager.liquidate(cdp2);
        CdpInfo memory cdp2After = getCdpInfo(cdp2);
        UserBalance memory liquidatorAfter = getUserBalance(liquidator);
        assertEq(liquidatorAfter.debt, 0);
        // note that cdp2 stETH collateral was just ~0,000001650000000001 stETH
        // that more or less are worth ~0,002768007
        assertApproxEqAbs(liquidatorAfter.coll, GAS_STIPEND + cdp2Before.collStETH, 1);
        // Assert that cdp2 has been fully liquidated
        assertEq(cdp2After.status, 3); // closedByLiquidation
        vm.revertTo(snapshot);
        ////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////
        // SUBSCENARIO 2: oracle price decrease, stETH share value decrease even more
        // The main difference in this scenario is that the stETH shares
        // (used by protocol for accounting) are worth less (compared to scenario 1)
        // This influence not only how much is worth the collateral you are gaining from the liquidation
        // but also the GAS STIPEND that you gain from the full liquidation
        // The GAS STIPEND is equal to `0.2 stETH` but at the time that the CDP (liquidated) was opened
        // if during this period the `stETH share` has decreased in value, also the GAS STIPEND
        // (that is denominated in converted shares) has decreased in value
        // This mean that the liquidator will receive less than `0.2 stETH` for the GAS STIPEND
        ////////////////////////////////////////////////////////////////////////////
        ////////////////////////////////////////////////////////////////////////////
        // bring the stETH share value down more to prove our scenario
        collateral.setEthPerShare(0.9 ether);
        // Liquidation is much less profittable and gas cost to execute the transaction could
        // be above the gas stipend (because now stETH share is less valuable)
        cdp2Before = getCdpInfo(cdp2);
        vm.prank(liquidator);
        cdpManager.liquidate(cdp2);
        cdp2After = getCdpInfo(cdp2);
        liquidatorAfter = getUserBalance(liquidator);
        // Assert that the profit from the liquidation is less than the GAS STIPEND
        assertLt(liquidatorAfter.coll, GAS_STIPEND);
        // Assert that cdp2 has been fully liquidated
        assertEq(cdp2After.status, 3); // closedByLiquidation
    }

    function testRedeemNotProfitable() public {
        _createDustCDPFromAdjust(0.0000001 ether);
        // let's make things easier to track by having a separate redeemer user
        // that holds 0 collateral and just the amount of eBTC needed to fully redeem CDP2
        (uint256 cdp2Debt, uint256 cdp2Coll, ) = cdpManager.getEntireDebtAndColl(cdp2);
        address redeemer = makeAddr("redeemer");
        // send to redeemer just what's needed to fully redeem cdp2
        vm.prank(user1);
        eBTCToken.transfer(redeemer, cdp2Debt);
        // prepare variables for later asserts
        UserBalance memory redeemerBefore = getUserBalance(redeemer);
        CdpInfo memory cdp1Before = getCdpInfo(cdp1);
        // perform the redeem of CDP2
        vm.prank(redeemer);
        cdpManager.redeemCollateral(cdp2Debt, bytes32(0), bytes32(0), bytes32(0), 0, 0, 1e18);
        UserBalance memory redeemerAfter = getUserBalance(redeemer);
        CdpInfo memory cdp1After = getCdpInfo(cdp1);
        // CDP has not changed (redeem operation has only fullly redeemed CDP2)
        assertEq(cdp1Before.debt, cdp1After.debt);
        assertEq(cdp1Before.coll, cdp1After.coll);
        // redeemer had only the amount of eBTC needed for the redemption
        assertEq(redeemerBefore.debt, cdp2Debt);
        // redeemer now has 0 eBTC (all of them used)
        assertEq(redeemerAfter.debt, 0);
        // redeemer had no collateral before the operation
        assertEq(redeemerBefore.coll, 0);
        // CDP2 has been closed
        assertEq(cdpManager.getCdpStatus(cdp2), 4); // closedByRedemption
        console.log("redeemerAfter.coll", redeemerAfter.coll);
        // in our test scenario gas cost for the operation is ~0.0207 ETH
        // assert that it was not profitable
        assertLt(redeemerAfter.coll, 0.0207 ether);
    }

    function calcStake(bytes32 cdpId) public view returns (uint256) {
        (uint realDebt, uint realColl, uint pendingEBTCDebtReward) = cdpManager.getEntireDebtAndColl(cdpId);
        return (realColl * cdpManager.totalStakesSnapshot()) / cdpManager.totalCollateralSnapshot();
    }

    function camputeICR(uint256 cdpCollShares, uint256 cdpDebt) public returns (uint256) {
        uint256 price = priceFeedMock.fetchPrice();
        uint256 coll = collateral.getPooledEthByShares(cdpCollShares);
        return (coll * price) / cdpDebt;
    }

    function getMaxLiquidableDebt(uint256 cdpDebt) public returns (uint256) {
        // needed for the check they are doing during partial liquidation
        uint256 price = priceFeedMock.fetchPrice();
        return cdpDebt - ((MIN_COLLAERAL_SIZE * price) / DECIMAL_PRECISION);
    }

    function maxWithdraw(uint256 cdpCollShares, uint256 cdpDebt) public returns (uint256) {
        // how much collateral can I withdraw to still be above MCR with the new ICR?
        uint256 price = priceFeedMock.fetchPrice();
        uint256 coll = collateral.getPooledEthByShares(cdpCollShares);
        uint256 maxWithdrawColl = coll - ((MCR * cdpDebt) / price);
        // remove 1 wei for rounding errors
        return maxWithdrawColl - 1;
    }

    function printSystem() public {
        console.log("=== PRINT SYSTEM ===");
        uint256 price = priceFeedMock.fetchPrice();
        uint256 tcr = cdpManager.getTCR(price);
        console.log("L_EBTCDebt ->", cdpManager.L_EBTCDebt());
        console.log("stFeePerUnitg ->", cdpManager.stFeePerUnitg());
        console.log("TCR ->", tcr);
        console.log("RM ? ->", tcr < CCR);
        console.log("");
    }

    function printCdp(bytes32 cdpId) public {
        (uint256 realDebt, uint256 realColl, ) = cdpManager.getEntireDebtAndColl(cdpId);
        uint256 price = priceFeedMock.fetchPrice();
        console.log("=== PRINT CDP ===");
        uint256 tcr = cdpManager.getTCR(price);
        uint256 icr = cdpManager.getCurrentICR(cdpId, price);
        bool liquidable = icr < MINIMAL_COLLATERAL_RATIO || (tcr < CCR && icr < tcr);
        uint256 coll = cdpManager.getCdpColl(cdpId);
        uint256 debt = cdpManager.getCdpDebt(cdpId);
        // try this
        coll = realColl;
        debt = realDebt;
        // try this
        uint collSt = collateral.getPooledEthByShares(coll);
        console.log("status ->", cdpManager.getCdpStatus(cdpId));
        console.log("stake ->", cdpManager.getCdpStake(cdpId));
        console.log("coll ->", coll);
        console.log("coll st ->", collSt);
        console.log("debt ->", debt);
        console.log("ICR ->", icr);
        console.log("liq? -> ", liquidable);
        console.log("minColl? -> ", collSt < MIN_COLLAERAL_SIZE);
        console.log("");
    }

    function getCdpInfo(bytes32 cdpId) public view returns (CdpInfo memory) {
        (uint realDebt, uint realColl, ) = cdpManager.getEntireDebtAndColl(cdpId);
        return CdpInfo(
            cdpManager.getCdpStatus(cdpId),
            realColl,
            collateral.getPooledEthByShares(realColl),
            realDebt
        );
    }

    function getUserBalance(address user) public view returns (UserBalance memory) {
        uint256 debt = eBTCToken.balanceOf(user);
        uint256 coll = collateral.balanceOf(user);
        return UserBalance(coll, debt);
    }

    struct CdpInfo {
        uint status;
        uint256 coll;
        uint256 collStETH;
        uint256 debt;
    }

    struct UserBalance {
        uint256 coll;
        uint256 debt;
    }
}
```

## Proof of Concept

no poc

## Recommendation

1. Badger should consider to always require, no matter what, that the CDP's collateral balance is always above the MIN_NET_COLL after the execution of BorrowerOperations._adjustCdpInternal and LiquidationLibrary._liquidateCDPPartially. It looks like _requirePartialLiqDebtSize() and _convertDebtDenominationToBtc() functions will be no longer needed:

• LiquidationLibrary.sol#L960-L969
```solidity
function _requirePartialLiqDebtSize(
    uint _partialDebt,
    uint _entireDebt,
    uint _price
) internal view {
    require(
        (_partialDebt + _convertDebtDenominationToBtc(MIN_NET_COLL, _price)) <= _entireDebt,
        "LiquidationLibrary: Partial debt liquidated must be less than total debt"
    );
}
```

• LiquityBase.sol#L106-L111
```solidity
// Convert debt denominated in ETH to debt denominated in BTC given that _price is ETH/BTC
// _debt is denominated in ETH
// _price is ETH/BTC
function _convertDebtDenominationToBtc(uint _debt, uint _price) internal pure returns (uint) {
    return (_debt * _price) / DECIMAL_PRECISION;
}
```

and can be removed (there are no other usages):

• LiquidationLibrary.sol#L340-L348
```solidity
function _liquidateCDPPartially(
    LocalVar_InternalLiquidate memory _partialState
) private returns (uint256, uint256) {
    bytes32 _cdpId = _partialState._cdpId;
    uint _partialDebt = _partialState._partialAmount;
    // calculate entire debt to repay
    LocalVar_CdpDebtColl memory _debtAndColl = _getEntireDebtAndColl(_cdpId);
    _requirePartialLiqDebtSize(_partialDebt, _debtAndColl.entireDebt, _partialState._price);
```

2. Badger should also consider removing the dependency to stETH from the LIQUIDATOR_REWARD (gas stipend). By doing so, the reward for the liquidator will always be 0.2 ETH without any influence from:

• stETH share value at the moment of the liquidation.

• stETH peg to ETH.

• stETH value in the market.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of allowing the creation of CDPs whose net collateral falls below the protocol‑defined constant MIN_NET_COLL (2 stETH) while still satisfying the collateral‑to‑debt ratio checks. This situation arises because BorrowerOperations._adjustCdpInternal and LiquidationLibrary._liquidateCDPPartially only verify that the individual collateral‑to‑debt ratio (ICR) stays above the minimum collateral ratio (MCR) and that the system‑wide TCR stays above the critical collateral ratio (CCR). They do not enforce an absolute lower bound on the amount of collateral that remains in the CDP after an adjustment or a partial liquidation. When the function collateral.getPooledEthByShares(DECIMAL_PRECISION) becomes smaller than DECIMAL_PRECISION – for example after a tiny reduction in the stETH share value (1 wei) – the contract permits the CDP’s collateral balance to drop below MIN_NET_COLL. An attacker (or a careless user) can therefore adjust a CDP to retain a negligible amount of debt (e.g., 0.0000001 eBTC) and withdraw almost all of the collateral, leaving a “dust CDP” with a few wei of stETH and a tiny debt. From the protocol’s perspective the CDP is still non‑liquidatable because its ICR remains just above MCR, so it is selected first for redemption and may also be targeted for partial liquidation. When a redeemer calls CdpManager.redeemCollateral, the system iterates over the lowest‑ICR CDPs that are still above MCR. The redeemer receives an amount of stETH proportional to the tiny debt of the dust CDP. Because the amount of stETH received (often only a few wei) is far smaller than the gas required to execute the redemption (≈0.02 ETH at 150 gwei, up to ≈0.08 ETH at 300 gwei), the operation yields a net loss. The redeemer therefore either loses money or abandons the transaction, reducing the effectiveness of the soft‑peg mechanism. A similar problem exists for liquidators: when a dust CDP is partially liquidated, the liquidator’s gas stipend of 0.2 stETH is converted into shares whose value may have decreased due to stETH slashing or peg deviation. If the stipend’s value falls below the gas cost of the liquidation (which can exceed 0.1 ETH for a full MEV liquidation), the liquidator incurs a loss or may simply refuse to liquidate, leaving under‑collateralised positions unaddressed. The impact is a reduction in economic incentives for both redeemers and liquidators, potential stagnation of liquidation queues, and a risk that the protocol’s stability mechanisms become ineffective. The issue is triggered only when the share‑to‑ETH conversion drops below one‑ether precision and when the contract’s internal checks do not enforce the MIN_NET_COLL threshold after adjustments. It affects borrowers who can create dust CDPs, redeemers who attempt to swap eBTC for collateral, liquidators who seek profit from under‑collateralised positions, and ultimately the protocol’s overall health. The bug was discovered during a manual audit by Spearbit, which reproduced the scenario in a Foundry test suite by opening a high‑collateral CDP, forcing a 1‑wei reduction in stETH share value, and then adjusting the CDP to leave a minimal debt and collateral. The problem is subtle because the standard safety checks (ICR > MCR, TCR > CCR) still pass, making the dust condition easy to miss in routine testing. To remediate, the protocol should enforce that after any adjustment or partial liquidation the CDP’s net collateral remains above MIN_NET_COLL, removing the reliance on the partial‑debt size check that currently permits dust creation. Additionally, decoupling the liquidator’s gas stipend from stETH share value – fixing it to a constant 0.2 ETH – would prevent the stipend from shrinking due to share‑price fluctuations, preserving liquidation incentives.
