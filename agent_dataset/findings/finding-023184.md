---
id: 23184
severity: "High"
---

# LiquidationLogic@_burnCollateralTokens

## Description

```solidity
library LiquidationLogic {
    function executeLiquidationCall(
        mapping(address => DataTypes.ReserveData) storage reservesData,
        mapping(uint256 => address) storage reservesList,
        mapping(address => mapping(bytes32 => DataTypes.PositionBalance)) storage balances,
        mapping(address => DataTypes.ReserveSupplies) storage totalSupplies,
        mapping(bytes32 => DataTypes.UserConfigurationMap) storage usersConfig,
        DataTypes.ExecuteLiquidationCallParams memory params
    ) external {
        (vars.actualCollateralToLiquidate, vars.actualDebtToLiquidate, vars.liquidationProtocolFeeAmount) = 
            _calculateAvailableCollateralToLiquidate(
                collateralReserve,
                vars.debtReserveCache,
                vars.actualDebtToLiquidate,
                vars.userCollateralBalance,
                vars.liquidationBonus,
                IPool(params.pool).getAssetPrice(params.collateralAsset),
                IPool(params.pool).getAssetPrice(params.debtAsset),
                IPool(params.pool).factory().liquidationProtocolFeePercentage()
            );
        _burnCollateralTokens(
            collateralReserve, params, vars,
            balances[params.collateralAsset][params.position],
            totalSupplies[params.collateralAsset]
        );
        if (vars.liquidationProtocolFeeAmount != 0) {
            IERC20(params.collateralAsset).safeTransfer(IPool(params.pool).factory().treasury(), vars.liquidationProtocolFeeAmount);
        }
    }

    function _burnCollateralTokens(
        DataTypes.ReserveData storage collateralReserve,
        DataTypes.ExecuteLiquidationCallParams memory params,
        LiquidationCallLocalVars memory vars,
        DataTypes.PositionBalance storage balances,
        DataTypes.ReserveSupplies storage totalSupplies
    ) internal {
        balances.withdrawCollateral(totalSupplies, vars.actualCollateralToLiquidate, collateralReserveCache.nextLiquidityIndex);
        // actualCollateralToLiquidate doesn't include liquidation fees
        IERC20(params.collateralAsset).safeTransfer(msg.sender, vars.actualCollateralToLiquidate);
    }

    function _calculateAvailableCollateralToLiquidate(
        DataTypes.ReserveData storage collateralReserve,
        DataTypes.ReserveCache memory debtReserveCache,
        uint256 debtToCover,
        uint256 userCollateralBalance,
        uint256 liquidationBonus,
        uint256 collateralPrice,
        uint256 debtAssetPrice,
        uint256 liquidationProtocolFeePercentage
    ) internal view returns (uint256, uint256, uint256) {
        if (liquidationProtocolFeePercentage != 0) {
            vars.bonusCollateral = vars.collateralAmount - vars.collateralAmount.percentDiv(liquidationBonus);
            vars.liquidationProtocolFee = vars.bonusCollateral.percentMul(liquidationProtocolFeePercentage);
            return (vars.collateralAmount - vars.liquidationProtocolFee, vars.debtAmountNeeded, vars.liquidationProtocolFee);
        } else {
            return (vars.collateralAmount, vars.debtAmountNeeded, 0);
        }
    }
}

function withdrawCollateral(
    DataTypes.PositionBalance storage self,
    DataTypes.ReserveSupplies storage supply,
    uint256 amount,
    uint128 index
) internal returns (uint256 sharesBurnt) {
    sharesBurnt = amount.rayDiv(index);
    require(sharesBurnt != 0, PoolErrorsLib.INVALID_BURN_AMOUNT);
    self.lastSupplyLiquidtyIndex = index;
}
```
When there are protocol liquidation fees, _burnCollateralTokens doesn't account for liquidation fees when withdrawing the collateral, leading to the pool and actor having more supply shares than reality.  
Internal pre-conditions  
Protocol liquidations fees are set.  
External pre-conditions  
N/A  
Attack Path  
Not an attack path per say as this happens in every liquidation when there are liquidation fees.  
1. Alice supplies tokenA  
2. Bob supplies tokenB  
3. Alice borrows tokenB  
4. Alice becomes liquidatable  
5. Bob liquidates Alice  
• Incorrect accounting : pool and actor supply shares are higher than reality, allowing a liquidated actor to borrow more than what they should really be able to for example.  
• Pools insolvency : since the liquidation fees are transferred to the treasury from the pool but not reflected on the pool and actor supply shares, the actor can withdraw them again at the expense of other actors. This leads to the other actors not being able to fully withdraw their provided collateral and potentially disrupting functionality such as Curated Vaults reallocation where the withdrawn amount cannot be controlled.

## Proof of Concept

```solidity
function testLiquidationWithFees() external {
    poolFactory.setLiquidationProtcolFeePercentage(0.05e4);
    _mintAndApprove(alice, tokenA, 3000 ether, address(pool));
    _mintAndApprove(bob, tokenB, 5000 ether, address(pool));
    vm.startPrank(bob);
    pool.supplySimple(address(tokenB), bob, 3000 ether, 0);
    vm.stopPrank();
    vm.startPrank(alice);
    pool.supplySimple(address(tokenA), alice, 1000 ether, 0);
    pool.borrowSimple(address(tokenB), alice, 375 ether, 0);
    vm.stopPrank();
    oracleB.updateAnswer(2.5e8);
    vm.prank(bob);
    pool.liquidateSimple(address(tokenA), address(tokenB), pos, type(uint256).max);
    assertEq(pool.getBalance(address(tokenA), alice, 0), tokenA.balanceOf(address(pool)));
}
```
Results  
forge test --match-test testLiquidationWithFees  
[✔] Compiling...  
No files changed, compilation skipped  
Ran 1 test for test/forge/core/pool/PoolLiquidationTests.t.sol:PoolLiquidationTest  
[FAIL. Reason: assertion failed: 17968750000000000000 != 15625000000000000000] testLiquidationWithFees() (gas: 1003975)  
Suite result: FAILED. 0 passed; 1 failed; 0 skipped; finished in 5.25ms (1.62ms CPU time)  
Ran 1 test suite in 347.96ms (5.25ms CPU time): 0 tests passed, 1 failed, 0 skipped (1 total tests)  
Failing tests:  
Encountered 1 failing test in test/forge/core/pool/PoolLiquidationTests.t.sol:PoolLiquidationTest  
[FAIL. Reason: assertion failed: 17968750000000000000 != 15625000000000000000] testLiquidationWithFees() (gas: 1003975)  
Encountered a total of 1 failing tests, 0 tests succeeded

## Recommendation

```diff
diff --git a/zerolend-one/contracts/core/pool/logic/LiquidationLogic.sol b/zerolend-one/contracts/core/pool/logic/LiquidationLogic.sol
index e89d626..0a48da6 100644
--- a/zerolend-one/contracts/core/pool/logic/LiquidationLogic.sol
+++ b/zerolend-one/contracts/core/pool/logic/LiquidationLogic.sol
@@ -225,7 +225,7 @@ library LiquidationLogic {
);
// Burn the equivalent amount of aToken, sending the underlying to the liquidator
- balances.withdrawCollateral(totalSupplies, vars.actualCollateralToLiquidate, collateralReserveCache.nextLiquidityIndex);
+ balances.withdrawCollateral(totalSupplies, vars.actualCollateralToLiquidate + vars.liquidationProtocolFeeAmount, collateralReserveCache.nextLiquidityIndex);
IERC20(params.collateralAsset).safeTransfer(msg.sender, vars.actualCollateralToLiquidate);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the liquidation routine of the protocol where the function that burns a liquidator’s collateral tokens does not include the protocol liquidation fee in the amount of collateral that is withdrawn from the borrower’s position. When the protocol fee percentage is non‑zero, the fee amount is transferred to the treasury but the internal accounting of supply shares is left unchanged because the withdrawCollateral call is made with only the net collateral amount (vars.actualCollateralToLiquidate). As a result the pool’s total supply shares and the liquidator’s share balance are inflated relative to the actual underlying assets held by the pool. This mismatch allows a liquidated actor to later withdraw more assets than they are entitled to, effectively letting the fee be reclaimed by the liquidator or other users and causing the pool to become insolvent. The issue manifests during any liquidation that includes a protocol fee, which is a common configuration for many lending markets. It affects borrowers who become liquidated, liquidators who receive the inflated shares, and all other depositors whose withdrawals may be short‑changed. The flaw was discovered during a security audit when a test that enabled a 5 % liquidation fee produced a failed assertion: the pool balance after liquidation did not match the expected amount, exposing the accounting error. The problem is subtle because the fee transfer appears to succeed and no explicit error is thrown; the discrepancy only shows up in aggregate share calculations, making it hard to notice in normal operation. Conceptually the fix is to adjust the withdrawCollateral call to include the fee amount (vars.liquidationProtocolFeeAmount) so that the total shares burned reflect the true amount of collateral removed from the pool, thereby keeping the supply accounting consistent with the underlying token balances. This class of bug is an accounting inconsistency caused by neglecting fee deductions in token burn logic, leading to money disappearing from the pool and violating the protocol’s accounting invariants.
