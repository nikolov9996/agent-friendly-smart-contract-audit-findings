---
id: 25155
severity: "Medium"
---

# Liquidations will leave dust when repaying expired maturities, making it impossible to clear bad debt putting the protocol at a risk of insolvency

## Description



## Proof of Concept

Place the following test in `Market.t.sol`. Notice how it reverts due to `ZERO_WITHDRAW` as the `actualRepayAssets` is zero.

```solidity
function test_POC_ClearBadDebt_Impossible_DueToDust() external {
  uint256 maxVal = type(uint256).max;

  market.deposit(10000 ether, address(this));

  vm.startPrank(BOB);
  market.deposit(100 ether, BOB);
  market.borrowAtMaturity(4 weeks, 60e18, maxVal, BOB, BOB);
  vm.stopPrank();

  vm.startPrank(ALICE);
  market.deposit(10, ALICE);
  market.borrowAtMaturity(4 weeks, 1, maxVal, ALICE, ALICE);
  vm.stopPrank();

  skip(20 weeks);

  (uint256 coll, uint256 debt) = market.accountSnapshot(BOB);
  console.log(coll);
  console.log(debt);

  vm.startPrank(ALICE);
  market.liquidate(BOB, 100_000 ether, market);
  vm.stopPrank();
  (coll, debt) = market.accountSnapshot(BOB);
  console.log(coll);
  console.log(debt);

  vm.startPrank(ALICE);
  market.liquidate(BOB, 100_000 ether, market);
  vm.stopPrank();
  (coll, debt) = market.accountSnapshot(BOB);
  console.log(coll);
  console.log(debt);

  vm.startPrank(ALICE);
  vm.expectRevert(); // ZERO WITHDRAW
  market.liquidate(BOB, 100_000 ether, market);
  vm.stopPrank();
}
```

## Impact

When there are expired maturities and the debt is bigger than the collateral `clearBadDebt()` will not be called, not even if liquidated successively.

## Recommendation

The mentioned rounding error is hard to deal with, it's easier to set some threshold to clear bad debt so rounding errors can be disregarded.
