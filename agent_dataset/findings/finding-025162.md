---
id: 25162
severity: "Medium"
---

# Liquidation does not prioritize lowest LTV tokens

## Description



## Proof of Concept

## Vulnerability Detail

At the moment of calculating the health factor, the user's collateral balance (in `ETH`) is multiplied by each asset's adjust factor and divided by the user's debt which is also divided by this adjust factor.

When liquidations are triggered, the liquidator decides in which asset the borrower will pay (choosing the seize market). However, there are not checks to see if that seize will improve health factor. When the borrower is collateralized through multiple assets, its borrowing power depends on the amount of collateral deposited and the average Risk-Adjust factor of all deposited assets. If a liquidator lowers this average Risk-Adjust factor by using as seize market the one that has the highest LTV asset in the borrower basket, the health factor of the borrower will decrease or not improve letting the liquidator liquidate the borrower again.

A precise mathematical explanation of how it works can be found on the [math paper](<https://docs.exact.ly/resources/math-paper#id-6.-liquidations>): ![[risk-adjust-factor-exactly.png]]

For example, let's say we deposited: 100 ETH of value in DAI with an adjusted factor of 0.9; 100 ETH of value in ETH with an adjusted factor of 0.3. Then, we borrow 42 ETH in DAI and 21 ETH in ETH. Consider at this point just for the practical example that the value of DAI is 2 ETH.

- The adjusted collateral will be equal to: `100*0.9 + 100*0.3 = 120`
- The adjusted debt will be equal to: `42/0.9 + 21/0.3 = 116.66
- The health factor will be equal to: `120/116.66 = 1.02`

The price of DAI drops and its value now is 1 ETH and now we have the same amount of debt in each asset (21 ETH in DAI and 30 ETH in ETH).

- The adjusted collateral will be equal to: `50*0.9 + 100*0.3 = 75`
- The adjusted debt will be equal to: `21/0.9 + 21/0.3 = 93.33`
- The health factor will be equal to: `75/93.33 = 0.80`

Partial liquidation can be triggered in two ways:

1. Clearing the borrower DAI debt This means that the token minted by the market that has DAI as underlying asset will be burned from the borrower account (the actual calculation process is a little bit different but the concept is the same).

Burning 21 ETH in value of DAI (at this point the conversion is 1:1) taking into account liquidator fee:

- The adjusted collateral will be equal to: `(29 - 21*0.05)0.9 + 1000.3 = 55.15`
- The adjusted debt will be equal to: `21/0.3 = 70`
- The health factor will be equal to: `55.15/70 = 0.78`

2. Clearing the borrower ETH debt Burning 21 ETH in value of ETH (at this point the conversion is 1:1) taking into account liquidator fee:

- The adjusted collateral will be equal to: `50*0.9 + (79 - 21*0.05)*0.3 = 68.38`
- The adjusted debt will be equal to: `21/0.9 = 23.33`
- The health factor will be equal to: `68.68/23.33 = 2.93`

In the case N°1, a minimized example of what occurs in the liquidation process is shown. However, for a more precise example refer to the PoC and to the math paper: [https://docs.exact.ly/resources/math-paper#id-6.-liquidations.](<https://docs.exact.ly/resources/math-paper#id-6.-liquidations>) Liquidations should always improve the Heath Factor.

A conceptual (not exact) explanation of this vulnerability: [https://youtu.be/AD2IF8ovE-w?si=nUgUn5berQdDgRN2&t=1884.](<https://youtu.be/AD2IF8ovE-w?si=nUgUn5berQdDgRN2&amp;t=1884>)

Given this scenario, in Exactly, the liquidator decides which asset the borrower will use to pay the debt. In this protocol and in many others, the possibility to execute partial liquidations is introduced to return the account to solvency as fast as possible and involve the least liquidation possible. The problem with this is that the protocol is allowing liquidators to lower the Health Factor of borrowers unnecessarily, benefiting liquidators and harming the borrower and the protocol, even putting the protocol in risk of a [liquidation crisis](<https://medium.com/coinmonks/what-is-liquidation-in-defi-lending-and-borrowing-platforms-3326e0ba8d0>).

Health factor after liquidations should always improve.

**Proof of Concept/Code:** Add `import { console } from "forge-std/console.sol"` to `test/Market.t.sol`

Add the following test on `test/Market.t.sol`

```solidity
function testLiquidationDoesntImproveHealthFactor() public {
    // modify adjust factor from set up
    auditor.setAdjustFactor(marketWETH, 0.3e18); // risk factor for some volatile asset e.g OP
    auditor.setAdjustFactor(market, 0.9e18); // risk factor for some stablecoin

    // providing some liquidity
    marketWETH.deposit(100_000 ether, address(this));
    market.deposit(100_000 ether, address(this));

    assertEq(market.balanceOf(ALICE), 0);
    assertEq(marketWETH.balanceOf(ALICE), 0);

    // adding collateral to borrower account (ALICE)
    market.deposit(15_000 ether, ALICE);
    marketWETH.deposit(15_000 ether, ALICE);

    assertEq(market.balanceOf(ALICE), 15_000 ether);
    assertEq(marketWETH.balanceOf(ALICE), 15_000 ether);

    // entering both markets so when checking account liquidity both deposits are considered
    vm.startPrank(ALICE);
    auditor.enterMarket(marketWETH);
    auditor.enterMarket(market);
    vm.stopPrank();

    // setting DAI price to twice the price of ETH so then it drops and the value is the same
    // (just to make calculations easier)
    daiPriceFeed.setPrice(2e18);

    // taking some debt in both assets
    vm.startPrank(ALICE);
    marketWETH.borrow(4000 ether, ALICE, ALICE);
    market.borrow(8000 ether, ALICE, ALICE);
    vm.stopPrank();

    // DAI price drops, ALICE is liquidatable
    daiPriceFeed.setPrice(1e18);

    (uint256 collateral, uint256 debt) = auditor.accountLiquidity(ALICE, Market(address(0)), 0);
    uint256 healthFactorBefore = (collateral * 1e18) / debt;

   // ALICE is liquidated and the seize market is the highest LTV asset
    vm.prank(BOB);
    market.liquidate(ALICE, 6000 ether, market); // @audit-info changing the seize market to WETH will make the HF go up

    (collateral, debt) = auditor.accountLiquidity(ALICE, Market(address(0)), 0);
    uint256 healthFactorAfter = (collateral * 1e18) / debt;

    console.log("Balance market after liq: ", market.balanceOf(ALICE));
    console.log("Balance marketweth after liq: ", marketWETH.balanceOf(ALICE));

    console.log("HF Before:", healthFactorBefore);
    console.log("HF After:", healthFactorAfter);

    // HEALTH FACTOR NOT IMPROVED!!!
    assert(healthFactorBefore >= healthFactorAfter);
  }
```

## Impact

Liquidators could unfairly liquidate borrowers no improving their health factor to liquidate them again. The protocol is at risk of a liquidation crisis.

## Code Snippet

[https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/Market.sol#L538-L614](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/Market.sol#L538-L614>) [https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/Auditor.sol#L195-L255](<https://github.com/sherlock-audit/2024-04-interest-rate-model/blob/8f6ef1b0868d3ea3a98a5ab7e8b3a164857681d7/protocol/contracts/Auditor.sol#L195-L255>)

## Recommendation

Add a check in the `liquidate` function to ensure that the health factor is improved after liquidation. A view function could be added so liquidators can check which markets can be used as seize market. However, addressing this issue can be complicated and could involve design decisions that I am not the one to propose.
