---
id: 25161
severity: "Medium"
---

# Market::liquidate() will not work when most of the liquidity is borrowed due to wrong liquidator transferFrom() order

## Description



## Proof of Concept

## Vulnerability Detail

The `transferFrom()` is called at the [end](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L613>) of the `Market::liquidate()` function, only receiving the assets after all the calculations.

However, when the seize market is the same as the repay market, the collateral to give to the liquidator will not be available if most of the liquidity is borrowed. Thus, it would require pulling the funds from the liquidator first and only then transferring them.

The following test confirms this behaviour, add it to `Market.t.sol`:

```solidity
function test_POC_NotEnoughAssetsDueToLiquidator_TransferFromAfter() external {
  auditor.setAdjustFactor(market, 0.9e18);

  vm.startPrank(ALICE);

  // ALICE deposits and borrows DAI
  uint256 assets = 10_000 ether;
  ERC20 asset = market.asset();
  deal(address(asset), ALICE, assets);
  market.deposit(assets, ALICE);
  market.borrow(assets*9*9/10/10, ALICE, ALICE);

  vm.stopPrank();

  skip(10 days);

  // LIQUIDATION fails as transfer from is after withdrawing collateral
  address liquidator = makeAddr("liquidator");
  vm.startPrank(liquidator);
  asset.approve(address(market), type(uint256).max);
  vm.expectRevert();
  market.liquidate(ALICE, type(uint256).max, market);
  vm.stopPrank();
}
```

## Impact

Impossible to liquidate when the repay market is the seize market and most of the liquidity is borrowed. A liquidator could deposit first into the market as a workaround fix but it would require close to double the funds (deposit so the contract has the funds and holding the funds to transfer to the market at the end of the call) to perform the liquidation, which could turn out to be expensive and would disincentivize liquidations, leading to accumulation of bad debt.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L613](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L613>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L693](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/main/protocol/contracts/Market.sol#L693>)

## Recommendation

The assets could be transferred from the liquidator to the market at the beginning of the liquidation. Alternatively, as the current code first transfers to the liquidator only to receive it back later, one option would be transferring only the different between the seize funds and the repaid debt (`liquidationIncentive.liquidator`) when `seizeMarket == repayMarket`.
