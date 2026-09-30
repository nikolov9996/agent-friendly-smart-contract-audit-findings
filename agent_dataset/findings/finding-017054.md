---
id: 17054
severity: "High"
---

# Interest rates are incorrect on Liquidation

## Description

The debt tokens are being transferred before calculating the interest rates. But the interest rate calculation function assumes that debt token has not yet been sent thus the outcome `currentLiquidityRate` will be incorrect

## Proof of Concept

1. Liquidator L1 calls [`executeLiquidateERC20`](https://github.com/code-423n4/2022-11-paraspace/blob/main/paraspace-core/contracts/protocol/libraries/logic/LiquidationLogic.sol#L161) for a position whose health factor <1

    ```solidity
    function executeLiquidateERC20(
        mapping(address => DataTypes.ReserveData) storage reservesData,
        mapping(uint256 => address) storage reservesList,
        mapping(address => DataTypes.UserConfigurationMap) storage usersConfig,
        DataTypes.ExecuteLiquidateParams memory params
    ) external returns (uint256) {
    ...
     _burnDebtTokens(liquidationAssetReserve, params, vars);
    ...
    }
    ```

2. This internally calls [`_burnDebtTokens`](https://github.com/code-423n4/2022-11-paraspace/blob/main/paraspace-core/contracts/protocol/libraries/logic/LiquidationLogic.sol#L523)

    ```solidity
    function _burnDebtTokens(
        DataTypes.ReserveData storage liquidationAssetReserve,
        DataTypes.ExecuteLiquidateParams memory params,
        ExecuteLiquidateLocalVars memory vars
    ) internal {
       ...
    
        // Transfers the debt asset being repaid to the xToken, where the liquidity is kept
        IERC20(params.liquidationAsset).safeTransferFrom(
            vars.payer,
            vars.liquidationAssetReserveCache.xTokenAddress,
            vars.actualLiquidationAmount
        );
    ...
        // Update borrow & supply rate
        liquidationAssetReserve.updateInterestRates(
            vars.liquidationAssetReserveCache,
            params.liquidationAsset,
            vars.actualLiquidationAmount,
            0
        );
    }
    ```

3. Basically first it transfers the debt asset to xToken using below. This increases the balance of xTokenAddress for liquidationAsset

    ```solidity
    IERC20(params.liquidationAsset).safeTransferFrom(
        vars.payer,
        vars.liquidationAssetReserveCache.xTokenAddress,
        vars.actualLiquidationAmount
    );
    ```

4. Now `updateInterestRates` function is called on ReserveLogic.sol#L169

    ```solidity
    function updateInterestRates(
        DataTypes.ReserveData storage reserve,
        DataTypes.ReserveCache memory reserveCache,
        address reserveAddress,
        uint256 liquidityAdded,
        uint256 liquidityTaken
    ) internal {
    ...
    (
        vars.nextLiquidityRate,
        vars.nextVariableRate
    ) = IReserveInterestRateStrategy(reserve.interestRateStrategyAddress)
        .calculateInterestRates(
            DataTypes.CalculateInterestRatesParams({
                liquidityAdded: liquidityAdded,
                liquidityTaken: liquidityTaken,
                totalVariableDebt: vars.totalVariableDebt,
                reserveFactor: reserveCache.reserveFactor,
                reserve: reserveAddress,
                xToken: reserveCache.xTokenAddress
            })
        );
    ...
    }
    ```

5. Finally call to `calculateInterestRates` function on DefaultReserveInterestRateStrategy#L127 contract is made which calculates the interest rate

    ```solidity
    function calculateInterestRates(
        DataTypes.CalculateInterestRatesParams calldata params
    ) external view override returns (uint256, uint256) {
    ...
    if (vars.totalDebt != 0) {
        vars.availableLiquidity =
            IToken(params.reserve).balanceOf(params.xToken) +
            params.liquidityAdded -
            params.liquidityTaken;

        vars.availableLiquidityPlusDebt =
            vars.availableLiquidity +
            vars.totalDebt;
        vars.borrowUsageRatio = vars.totalDebt.rayDiv(
            vars.availableLiquidityPlusDebt
        );
        vars.supplyUsageRatio = vars.totalDebt.rayDiv(
            vars.availableLiquidityPlusDebt
        );
    }
    ...
    vars.currentLiquidityRate = vars
        .currentVariableBorrowRate
        .rayMul(vars.supplyUsageRatio)
        .percentMul(
            PercentageMath.PERCENTAGE_FACTOR - params.reserveFactor
        );

    return (vars.currentLiquidityRate, vars.currentVariableBorrowRate);
    }
    ```

6. As we can see in above code, `vars.availableLiquidity` is calculated as `IToken(params.reserve).balanceOf(params.xToken) + params.liquidityAdded - params.liquidityTaken`
7. But the problem is that debt token is already transferred to `xToken` which means `xToken` already consist of `params.liquidityAdded`. Hence the calculation ultimately becomes `(xTokenBeforeBalance + params.liquidityAdded) + params.liquidityAdded - params.liquidityTaken`
8. This is incorrect and would lead to higher `vars.availableLiquidity` which ultimately impacts the `currentLiquidityRate`

## Recommendation

Transfer the debt asset post interest calculation

```solidity
function _burnDebtTokens(
    DataTypes.ReserveData storage liquidationAssetReserve,
    DataTypes.ExecuteLiquidateParams memory params,
    ExecuteLiquidateLocalVars memory vars
) internal {
    IPToken(vars.liquidationAssetReserveCache.xTokenAddress)
        .handleRepayment(params.liquidator, vars.actualLiquidationAmount);
    // Burn borrower's debt token
    vars
        .liquidationAssetReserveCache
        .nextScaledVariableDebt = IVariableDebtToken(
        vars.liquidationAssetReserveCache.variableDebtTokenAddress
    ).burn(
        params.borrower,
        vars.actualLiquidationAmount,
        vars.liquidationAssetReserveCache.nextVariableBorrowIndex
    );

    liquidationAssetReserve.updateInterestRates(
        vars.liquidationAssetReserveCache,
        params.liquidationAsset,
        vars.actualLiquidationAmount,
        0
    );
    IERC20(params.liquidationAsset).safeTransferFrom(
        vars.payer,
        vars.liquidationAssetReserveCache.xTokenAddress,
        vars.actualLiquidationAmount
    );
    ...
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an ordering error in the liquidation flow that leads to an inaccurate computation of the reserve’s interest rates. When a liquidator repays a borrower’s debt, the implementation first transfers the repayment amount to the reserve’s xToken (the contract that holds liquidity) and only afterwards invokes the reserve’s updateInterestRates routine. The interest‑rate calculation routine assumes that the transferred amount has not yet been added to the reserve’s available liquidity, and therefore it adds the repayment amount (liquidityAdded) on top of the current xToken balance. Because the balance already includes the transferred funds, the algorithm ends up counting the same amount twice: once implicitly via the updated token balance and again explicitly through the liquidityAdded parameter. This double‑count inflates the reported availableLiquidity, which in turn skews the derived supply‑usage ratio and consequently produces a currentLiquidityRate that deviates from the correct value. The bug manifests only during liquidation transactions where the liquidator’s repayment is processed, and it does not affect ordinary supply or borrow operations that calculate rates after the balance update. Any user, lender, or borrower interacting with the protocol during a liquidation can see the effects: the UI may display a higher or lower supply rate than warranted, lenders receive less interest than they should, and borrowers may be charged an incorrect borrowing cost. Because the rate discrepancy is subtle – it appears as a small deviation in an otherwise smooth curve – it can be difficult to detect without explicit comparison against a trusted model or a detailed unit test that isolates the ordering of state changes. The problem was uncovered during a formal audit by Code4rena, where the auditors traced the liquidation path, observed the premature transfer, and identified the mismatch in the interest‑rate formula. The core of the issue belongs to the class of accounting bugs caused by improper sequencing of state mutations, often referred to as “double‑counting” or “order‑of‑operations” errors. To remediate the flaw, the protocol should postpone the token transfer until after the interest‑rate update, or alternatively adjust the calculation to exclude the already‑credited amount when liquidityAdded is supplied. By ensuring that the reserve’s liquidity snapshot reflects the state before the transfer, the derived rates will align with the protocol’s economic assumptions and preserve the integrity of lender rewards and borrower costs.
