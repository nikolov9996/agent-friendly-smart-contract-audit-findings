---
id: 25154
severity: "Medium"
---

# Liquidating maturies with unassigned earnings will not take into account floating assets increase leading to loss of funds

## Description



## Proof of Concept

Add the following test to `Market.t.sol`, confirming that the user should have all its collateral seized given that debt > collateral but some collateral remains due to the increase in floating assets.

```solidity
function test_POC_FloatingAssetsIncrease() external {
  uint256 maxVal = type(uint256).max;

  market.deposit(10000 ether, address(this));

  vm.startPrank(BOB);
  market.deposit(100 ether, BOB);
  market.borrowAtMaturity(4 weeks, 60e18, maxVal, BOB, BOB);
  vm.stopPrank();

  skip(10 weeks);

  (uint256 coll, uint256 debt) = market.accountSnapshot(BOB);
  assertEq(coll, 100e18);
  assertEq(debt, 111.246904109483404820e18);

  vm.startPrank(ALICE);
  market.liquidate(BOB, 100_000 ether, market);
  vm.stopPrank();

  (coll, debt) = market.accountSnapshot(BOB);
  assertEq(coll, 4.557168045571680e15);
  assertEq(debt, 20.337813200392495730e18);
}
```

## Impact

If the user has less debt than collateral but the debt would require most of its collateral, it would not be possible to seize it all. If the user has more debt than collateral a portion of the collateral will be leftover which will not allow bad debt to be cleared right away via `clearBadDebt()` and stays accruing.

## Recommendation

`Auditor::checkLiquidation()` should compute the increase in collateral by previewing the floating assets increase due to accrued unassigned earnings in a fixed pool or instead of increasing floating assets these earnings could increase the earnings accumulator.
