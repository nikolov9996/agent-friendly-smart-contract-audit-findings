---
id: 23164
severity: "High"
---

# Interest rate is updated before

## Description

Interest rate is updated before updating the debt when repaying debt in BorrowLogic@executeRepay leading to an incorrect total debt being used when calculating the new interest rates and causing suppliers to keep accruing interest based on the previous debt and even if there are no ongoing borrows anymore.
```solidity
BorrowLogic
function executeRepay(
    DataTypes.ReserveData storage reserve,
    DataTypes.PositionBalance storage balances,
    DataTypes.ReserveSupplies storage totalSupplies,
    DataTypes.UserConfigurationMap storage userConfig,
    DataTypes.ExecuteRepayParams memory params
) external returns (DataTypes.SharesType memory payback) {
    DataTypes.ReserveCache memory cache = reserve.cache(totalSupplies);
    reserve.updateState(params.reserveFactor, cache);
    payback.assets = balances.getDebtBalance(cache.nextBorrowIndex);
    // Allows a user to max repay without leaving dust from interest.
    if (params.amount == type(uint256).max) {
        params.amount = payback.assets;
    }
    ValidationLogic.validateRepay(params.amount, payback.assets);
    // If paybackAmount is more than what the user wants to payback, the set it to the
    // user input (ie params.amount)
    if (params.amount < payback.assets) payback.assets = params.amount;
    totalSupplies,
    cache,
    params.asset,
    IPool(params.pool).getReserveFactor(),
    payback.assets,
    0,
    params.position,
    params.data.interestRateData
    );
    // update balances and total supplies
    payback.shares = balances.repayDebt(totalSupplies, payback.assets,
    );
    if (balances.getDebtBalance(cache.nextBorrowIndex) == 0) {
        userConfig.setBorrowing(reserve.id, false);
    }
    IERC20(params.asset).safeTransferFrom(msg.sender, address(this), payback.assets);
    emit PoolEventsLib.Repay(params.asset, params.position, msg.sender,
    payback.assets);
}
```
```solidity
ReserveLogic
function updateInterestRates(
    DataTypes.ReserveData storage _reserve,
    DataTypes.ReserveSupplies storage totalSupplies,
    DataTypes.ReserveCache memory _cache,
    address _reserveAddress,
    uint256 _reserveFactor,
    uint256 _liquidityAdded,
    uint256 _liquidityTaken,
    bytes32 _position,
    bytes memory _data
) internal {
    UpdateInterestRatesLocalVars memory vars;
    vars.totalDebt = _cache.nextDebtShares.rayMul(_cache.nextBorrowIndex); // <====
    (vars.nextLiquidityRate, vars.nextBorrowRate) =
        IReserveInterestRateStrategy(_reserve.interestRateStrategyAddress)
        .calculateInterestRates(
            _position,
            _data,
            DataTypes.CalculateInterestRatesParams({
                liquidityTaken: _liquidityTaken,
                reserveFactor: _reserveFactor,
                reserve: _reserveAddress
            })
        );
    _reserve.liquidityRate = vars.nextLiquidityRate.toUint128();
    _reserve.borrowRate = vars.nextBorrowRate.toUint128();
    if (_liquidityAdded > 0) totalSupplies.underlyingBalance +=
        _liquidityAdded.toUint128();
    else if (_liquidityTaken > 0) totalSupplies.underlyingBalance -=
        _liquidityTaken.toUint128();
    emit PoolEventsLib.ReserveDataUpdated(
        _reserveAddress, vars.nextLiquidityRate, vars.nextBorrowRate,
        _cache.nextLiquidityIndex, _cache.nextBorrowIndex
    );
}
```
Interest rate is updated before repaying the debt and updating the cached nextDebtShares which is then used in the interest rate calculation causing it to return a wrong interest rate as it behaves like liquidity was just supplied by the borrower without a change in debt.
Internal pre-conditions
N/A
External pre-conditions
N/A
Attack Path
1. Bob supplies tokenB
2. Alice supplies tokenA
3. Alice borrows tokenB causing the utilization goes up and interest rate is updated
4. Bob starts accruing interest
5. Alice fully repays tokenB but the interest rate is not updated correctly
6. Bob keeps accruing interest
Bob keeps accruing interest rate based on the previous debt and even if there are no ongoing borrows and can withdraw it at the expense of other suppliers.

## Proof of Concept

```solidity
function testRepay() external {
    _mintAndApprove(alice, tokenA, 3000 ether, address(pool));
    _mintAndApprove(alice, tokenB, 1000 ether, address(pool));
    _mintAndApprove(bob, tokenB, 5000 ether, address(pool));
    vm.startPrank(bob);
    pool.supplySimple(address(tokenB), bob, 500 ether, 0);
    skip(12);
    vm.startPrank(alice);
    pool.supplySimple(address(tokenA), alice, 1000 ether, 0);
    skip(12);
    oracleA.updateRoundTimestamp();
    oracleB.updateRoundTimestamp();
    pool.borrowSimple(address(tokenB), alice, 375 ether, 0);
    skip(12);
    pool.repaySimple(address(tokenB), type(uint256).max, 0);
    vm.stopPrank();
    bytes32 bobPos = keccak256(abi.encodePacked(bob, 'index', uint256(0)));
    uint256 bobSupplyAssetsBefore = pool.supplyAssets(address(tokenB), bobPos);
    skip(24 * 30 * 60 * 60);
    pool.forceUpdateReserve(address(tokenB));
    assertGt(pool.supplyAssets(address(tokenB), bobPos), bobSupplyAssetsBefore); // Bob accrued interest even if there are no borrows anymore
    vm.startPrank(bob);
    // Reverts because Bob shares with the accrued interest exceed the pool balance but
    // succeed if there were other suppliers.
    vm.expectRevert();
    pool.withdrawSimple(address(tokenB), bob, type(uint256).max, 0);
    vm.stopPrank();
}
```

## Recommendation

```diff
diff --git a/zerolend-one/contracts/core/pool/logic/BorrowLogic.sol b/zerolend-one/contracts/core/pool/logic/BorrowLogic.sol
index 92806b1..c070fb1 100644
--- a/zerolend-one/contracts/core/pool/logic/BorrowLogic.sol
+++ b/zerolend-one/contracts/core/pool/logic/BorrowLogic.sol
@@ -136,6 +136,14 @@ library BorrowLogic {
// user input (ie params.amount)
if (params.amount < payback.assets) payback.assets = params.amount;
+
// update balances and total supplies
+
payback.shares = balances.repayDebt(totalSupplies, payback.assets,
cache.nextBorrowIndex);
+
cache.nextDebtShares = totalSupplies.debtShares;
+
+
if (balances.getDebtBalance(cache.nextBorrowIndex) == 0) {
+
userConfig.setBorrowing(reserve.id, false);
+
}
+
reserve.updateInterestRates(
totalSupplies,
cache,
@@ -147,14 +155,6 @@ library BorrowLogic {
params.data.interestRateData
);
-
// update balances and total supplies
-
payback.shares = balances.repayDebt(totalSupplies, payback.assets,
cache.nextBorrowIndex);
-
-
cache.nextDebtShares = totalSupplies.debtShares;
-
-
if (balances.getDebtBalance(cache.nextBorrowIndex) == 0) {
-
userConfig.setBorrowing(reserve.id, false);
-
}
-
IERC20(params.asset).safeTransferFrom(msg.sender, address(this),
payback.assets);
-
emit PoolEventsLib.Repay(params.asset, params.position, msg.sender,
payback.assets);
-
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an ordering flaw in the repayment flow of the lending pool. When a borrower calls the repay function, the contract updates the reserve’s interest rates before it has reduced the recorded total debt. The interest‑rate calculation reads the cached nextDebtShares value, which still reflects the pre‑repayment debt amount. Consequently the new liquidity and borrow rates are computed as if the debt had not changed, treating the repayment as a fresh liquidity injection rather than a debt reduction. This stale‑state usage allows the protocol to keep charging interest on a debt that is already zero. The bug manifests whenever a repayment clears a user’s outstanding borrow – including the special case where the caller passes type(uint256).max to repay the full amount. Under these conditions the protocol emits a correct Repay event, transfers the assets, but the subsequent call to updateInterestRates uses the old debt figure, leaving the reserve’s utilization unchanged. Suppliers who have provided liquidity therefore continue to accrue interest based on the previous, higher utilization, even though no borrowers remain. From a user’s perspective a supplier sees their supplied balance grow unexpectedly or, when trying to withdraw, encounters a revert because the pool’s internal accounting shows more shares than the actual token balance. The impact is a distortion of the accounting model: interest is over‑distributed to early suppliers and under‑distributed to later ones, and in extreme cases funds can become locked because the pool believes it owes more interest than it holds. The issue was discovered during a formal audit and reproduced with a test that repays a loan, skips time, forces a reserve update and then observes that the supplier’s accrued interest continues to increase and withdrawal fails. The problem is hard to notice because the interest‑rate values appear to update normally and the repayment transaction succeeds, hiding the fact that the underlying debt metric was never refreshed. The bug belongs to the class of state‑ordering or stale‑cache vulnerabilities, where a contract reads a value that should have been updated earlier in the same transaction. The correct fix is to move the call that updates the reserve’s interest rates to after the debt balance and cache variables have been refreshed – for example by updating cache.nextDebtShares (or the equivalent debt state) before invoking updateInterestRates, or by separating the two steps into distinct transactions. In conceptual terms the protocol must ensure that any interest‑rate computation uses the most recent debt snapshot, guaranteeing that interest accrues only on actual outstanding borrowings and that suppliers receive interest that matches the true utilization of the pool.
