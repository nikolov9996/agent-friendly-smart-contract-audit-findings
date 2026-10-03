---
id: 25148
severity: "Medium"
---

# TARGET_HEALTH calculation does not consider the adjust factors of the picked seize and repay markets

## Description



## Proof of Concept

## Vulnerability Detail

The calculation of the required debt to repay is explained in the [MathPaper](<https://github.com/exactly/papers/blob/main/ExactlyMathPaperV1.pdf>), and it can be understood that the resulting debt to repay is based on the average adjust factor of all markets.

However, when liquidating, repay and seize markets are picked, possibly having different adjust factors. Thus, depending on the picked repay and seized market, the resulting health factor will be significantly different than the `TARGET_HEALTH`. This will either lead to losses for the liquidator or the liquidatee, in case the resulting health factor is smaller or bigger, respectively.

If the resulting health factor is smaller, the liquidator would receive less assets and the protocol would be closer to accumulating bad debt (it may even be negative if the calculation is way off). Contrarily, if it is higher, the liquidator will have more assets removed than supposed, resulting in losses.

A test was carried out in `Market.t.sol` showing that depending on the market picked, the health factor is either approximately `1.37` or `1.15`, due to the adjust factor. The user

- Deposited `20_000e18` in a `DAI` market with an adjust factor of `0.8`.
- Borrowed `20_000e18*0.8^2` in the `DAI` market.
- Deposited `10_000e18` in a `WETH` market with an adjust factor of `0.9`.
- Borrowed `10_000e18*0.9^2` in a `WETH` market. The health factor is `(20_000*0.8 + 10000*0.9) / (20000*0.8^2/0.8 + 10000*0.9^2/0.9) = 1`. 1 second passes to make the health factor smaller than 1. Now, depending on the picked repay and seize markets, the resulting health factor will be very different.

The average adjust factor is `(20_000*0.8 + 10000*0.9)  (200000.8^2 + 10000*0.9^2) / (20000*0.8^2/0.8 + 10000*0.9^2/0.9) / (20000 + 10000) = 0.6967`.

The close factor is `(1.25 - 1) / (1.25 - 0.6967*1.1) = 0.5169`.

The debt repayed using the close factor is `(20000*0.8^2 + 10000*0.9^2)0.5169 = 10803`*. The Collateral repayed is `10803 `*` 1.1 = 11883`.

The issue is that the debt and collateral are averaged on the adjust factor, but it is being repayed on a single market.

Repaying in the `DAI` market, the resulting health factor is `((20_000 - 11883)0.8 + 100000.9) / ((20000*0.8^2 - 10803)/0.8 + 10000*0.9^2/0.9) = 1.3477`.

If the test is inverted, repaying in the `WETH` market will lead to a health factor of `1.15`.

```solidity
function test_POC_WrongHealthFactor() external {
  // Change to false to test liquidating in the WETH market
  // in exactly the same conditions except the adjust factor
  bool marketDAI = true;

  uint256 assets = 10_000 ether;
  ERC20 asset = market.asset();
  uint256 marketAssets = marketDAI ? 2*assets : assets;
  uint256 wethAssets = marketDAI ? assets : 2*assets;

  vm.startPrank(ALICE);

  // ALICE deposits and borrows DAI
  deal(address(asset), ALICE, marketAssets);
  market.deposit(marketAssets, ALICE);
  market.borrow(marketAssets*8*8/10/10, ALICE, ALICE);

  // ALICE deposits and borrows weth
  deal(address(weth), ALICE, wethAssets);
  weth.approve(address(marketWETH), wethAssets);
  marketWETH.deposit(wethAssets, ALICE);
  marketWETH.borrow(wethAssets*9*9/10/10, ALICE, ALICE);

  vm.stopPrank();

  skip(1);

  // LIQUIDATION of DAI MARKET, 0.8 adjust factor
  if (marketDAI) {
    deal(address(asset), address(market), 100_000 ether);
    address liquidator = makeAddr("liquidator");
    deal(address(asset), liquidator, 100_000_000 ether);
    vm.startPrank(liquidator);
    asset.approve(address(market), type(uint256).max);
    market.liquidate(ALICE, type(uint256).max, market);
    vm.stopPrank();
  }

  // LIQUIDATION of WETH MARKET, 0.9 adjust factor
  if (!marketDAI) {
    deal(address(weth), address(marketWETH), 100_000 ether);
    address liquidator = makeAddr("liquidator");
    deal(address(weth), liquidator, 100_000_000 ether);
    vm.startPrank(liquidator);
    weth.approve(address(marketWETH), type(uint256).max);
    marketWETH.liquidate(ALICE, type(uint256).max, marketWETH);
    vm.stopPrank();
  }

  // RATIO is smaller than 1.25, liquidator did not liquidate as much as if it was in
  // a single market
  (uint256 collateral, uint256 debt) = auditor.accountLiquidity(address(ALICE), Market(address(0)), 0);
  assertEq(collateral*1e18 / debt, marketDAI ? 1347680781176165186 : 1146310462433177450);
}
```

## Impact

Losses for the liquidator or the liquidatee and possible accumulation of bad debt, depending on the picked market.

## Code Snippet

[https://github.com/exactly/papers/blob/main/ExactlyMathPaperV1.pdf](<https://github.com/exactly/papers/blob/main/ExactlyMathPaperV1.pdf>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L238-L243](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Auditor.sol#L238-L243>)

## Recommendation

The debt to repay should take into account the adjust factors of the seize and repay markets. In `auditor::checkLiquidation()`, the `maxRepayAssets`, `base.totalDebt.mulWadUp(Math.min(1e18, closeFactor)), must consider the adjust factors of the chosen seize and repay markets.
