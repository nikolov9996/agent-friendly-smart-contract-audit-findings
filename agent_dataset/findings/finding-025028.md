---
id: 25028
severity: "Medium"
---

# Major insolvency risk in LiquidationLogic::executeCrossLiquidateERC721() due to not setting a maximum liquidation price

## Description



## Proof of Concept

In `LiquidationLogic::executeCrossLiquidateERC721()`, the actual debt to liquidate is calculated in [`LiquidationLogic::_calculateDebtAmountFromERC721Collateral()`](<https://github.com/code-423n4/2024-07-benddao/blob/main/src/libraries/logic/LiquidationLogic.sol#L202>). [Here](<https://github.com/code-423n4/2024-07-benddao/blob/main/src/libraries/logic/LiquidationLogic.sol#L500>), it calculates the price of the liquidated nft by dividing the debt by the number of collateral tokens the user has. The problem with this approach is that it places no upper limit on the price, such that if the debt increases to much or the nft price suffers a sudden loss; the price of each nft would be too high. The amount of debt to repay is calculated based on this price, so it would make no sense for liquidators to pay an inflated amount for each nft.

Additionally, it's possible to liquidate only a selected amount of nfts at a time by setting `params.collateralTokenIds.length` to less than the nft balance of the borrower, but it always sells them to the liquidator at the same inflated price. Thus, it's impossible to use this mechanism to repay some amount of debt at a profitable price for the liquidator.

Place the following test in `TestIntCrossLiquidateERC721.t.sol`, confirming that the liquidator takes a big loss if the price of the nft collateral drops significantly.

```
function test_POC_RepayUSDT_HasBAYC_InflatedPrice() public {
  prepareUSDT(tsDepositor1);

  uint256[] memory depTokenIds = prepareCrossBAYC(tsBorrower1);

  TestUserAccountData memory accountDataBeforeBorrow = getUserAccountData(address(tsBorrower1), tsCommonPoolId);

  // borrow some eth
  uint8[] memory borrowGroups = new uint8[](1);
  borrowGroups[0] = tsLowRateGroupId;

  uint256[] memory borrowAmounts = new uint256[](1);
  borrowAmounts[0] =
    (accountDataBeforeBorrow.availableBorrowInBase * (10 ** tsUSDT.decimals())) /
    tsPriceOracle.getAssetPrice(address(tsUSDT));

  actionCrossBorrowERC20(
    address(tsBorrower1),
    tsCommonPoolId,
    address(tsUSDT),
    borrowGroups,
    borrowAmounts,
    new bytes(0)
  );

  // make some interest
  advanceTimes(365 days);

  // drop down price and lower health factor
  uint256 baycCurPrice = tsBendNFTOracle.getAssetPrice(address(tsBAYC));
  uint256 baycNewPrice = (baycCurPrice * 60) / 100;
  tsBendNFTOracle.setAssetPrice(address(tsBAYC), baycNewPrice);

  TestUserAccountData memory accountDataAfterBorrow = getUserAccountData(address(tsBorrower1), tsCommonPoolId);
  assertLt(accountDataAfterBorrow.healthFactor, 1e18, 'ACC:healthFactor');

  (uint256 actualCollateralToLiquidate, uint256 actualDebtToLiquidate) = tsPoolLens.getUserCrossLiquidateData(
    tsCommonPoolId,
    address(tsBorrower1),
    address(tsBAYC),
    1,
    address(tsUSDT),
    0
  );

  uint256 tsBAYCprice = tsPriceOracle.getAssetPrice(address(tsBAYC));
  uint256 tsUSDTprice = tsPriceOracle.getAssetPrice(address(tsUSDT));
  assertEq(tsBAYCprice, 3822840829686);
  assertEq(tsUSDTprice, 100053000);

  uint256 collateralValue = tsBAYCprice;
  uint256 debtValue = actualDebtToLiquidate * tsUSDTprice / 1e6;
  assertEq(debtValue, 4300008062440, 'actualDebtToLiquidate');
  assertEq(debtValue * 100 / collateralValue, 112); //@audit debt is worth 112% of collateral, not worth it

  assertGt(actualDebtToLiquidate, 0, 'actualDebtToLiquidate');
  assertGt(actualCollateralToLiquidate, 0, 'actualCollateralToLiquidate');

  // liquidate some eth
  tsLiquidator1.approveERC20(address(tsUSDT), type(uint256).max);

  uint256[] memory liqTokenIds = new uint256[](1);
  liqTokenIds[0] = depTokenIds[0];

  actionCrossLiquidateERC721(
    address(tsLiquidator1),
    tsCommonPoolId,
    address(tsBorrower1),
    address(tsBAYC),
    liqTokenIds,
    address(tsUSDT),
    false,
    new bytes(0)
  );
}
```

## Recommendation

Cap the price per nft of the liquidation to a reasonable value so liquidators can at least repay some of the token ids of the position. This is how it works for `ERC20` liquidations, for example, in which the maximum debt to repay is calculated based on the maximum collateral balance sold at a discount.
