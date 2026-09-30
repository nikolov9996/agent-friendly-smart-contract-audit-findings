---
id: 18290
severity: "High"
---

# Incorrect calculation of `usedFunds` in LiquidityPool leads to lower than expected token price

## Description

In `LiquidityPool.sol`, the functions `openLong()`, `closeLong()`, `openShort()` and `closeShort()` do not deduct `hedgingFees` from `usedFunds` to offset the `hedgingFees` that was added due to `_hedge()`.

## Proof of Concept

Then add the following imports and test case to `test/LiquidityPool.Trades.t.sol`
    
```solidity
import {wadMul} from "solmate/utils/SignedWadMath.sol";
import {IPerpsV2Market} from "../src/interfaces/synthetix/IPerpsV2Market.sol";

function testLiquidityPoolFundCalculation() public {
    uint256 longAmount = 1e18;

    (uint256 markPrice, bool isInvalid) = pool.getMarkPrice();
    uint256 tradeCost = longAmount.mulWadDown(markPrice);
    uint256 fees = pool.orderFee(int256(longAmount)); 
    uint256 delta = pool.getDelta();
    int256 hedgingSize = wadMul(int256(longAmount), int256(delta));
    IPerpsV2Market perp = pool.perpMarket();
    (uint256 hedgingFees, ) = perp.orderFee(hedgingSize, IPerpsV2MarketBaseTypes.OrderType.Delayed);
    uint256 feesCollected = fees - hedgingFees;
    uint256 externalFee = feesCollected.mulWadDown(pool.devFee());

    uint256 totalFundsBefore = pool.totalFunds();
    int256 usedFundsBefore = pool.usedFunds();

    // Open a Long trade
    openLong(longAmount, longAmount * 1000, user_1);

    // Calculated expected totalFunds and usedFunds
    uint256 expectedTotalFunds = totalFundsBefore + feesCollected - externalFee;
    uint256 marginRequired = tradeCost + hedgingFees;
    int256 expectedUsedFunds = usedFundsBefore - int256(tradeCost) - int256(hedgingFees) + int256(marginRequired);

    // This is correct as the pool will increase by net fee (feesCollected - externalFee)
    assertEq(pool.totalFunds(), expectedTotalFunds);

    // LiquidityPool's UsedFunds is wrong and is higher than expected as it included hedgingFees.
    assertGt(pool.usedFunds(), expectedUsedFunds);

    uint256 poolAvailableFunds = pool.totalFunds() - uint256(pool.usedFunds());
    uint256 expectedAvailableFunds = expectedTotalFunds - uint256(expectedUsedFunds);
    
    // LiquidityPool's available funds is wrong and is less than expected as it factored in hedgingFees
    assertLt(poolAvailableFunds, expectedAvailableFunds);
    assertEq(poolAvailableFunds, expectedAvailableFunds - hedgingFees);

    // LiquidityPool's available funds is wrong and is also less than SUSD balance 
    assertLt(poolAvailableFunds, susd.balanceOf(address(pool)));

    // LiquidityPool's available fund is expected to be the same as Pool's SUSD balance
    assertEq(expectedAvailableFunds, susd.balanceOf(address(pool)));

    // LiquidityPool Token price is less than expected.
    assertLt(pool.getTokenPrice(), getExpectedTokenPrice(expectedTotalFunds, expectedUsedFunds, perp));
}

function getExpectedTokenPrice(uint256 expectedTotalFunds, int256 expectedUsedFunds, IPerpsV2Market perp) public returns (uint256 expectedTokenPrice) {
    (uint256 markPrice,) = pool.getMarkPrice();
    uint256 totalValue = expectedTotalFunds;
    uint256 totalSupply = lqToken.totalSupply() + pool.totalQueuedWithdrawals();
    uint256 amountOwed = markPrice.mulWadDown(powerPerp.totalSupply());
    uint256 amountToCollect = markPrice.mulWadDown(shortToken.totalShorts());

    (uint256 totalMargin,) = perp.remainingMargin(address(pool));

    totalValue += totalMargin + amountToCollect;
    totalValue -= uint256((int256(amountOwed) + expectedUsedFunds));

    expectedTokenPrice = totalValue.divWadDown(totalSupply);
}
```

## Recommendation

Deduct `hedgingFees` from `usedFunds` to offset the `hedgingFees` added in `_hedge()`.

For example, in openLong change
    
```solidity
usedFunds -= int256(tradeCost); 
```

to
    
```solidity
usedFunds -= int256(tradeCost) - int256(hedgingFees);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the accounting logic of the LiquidityPool contract where the internal variable usedFunds is updated incorrectly during trade operations. When a user opens or closes a long or short position, the contract calls an internal hedging routine that charges hedgingFees. The implementation adds these fees to the pool’s margin requirements but fails to subtract the same amount from usedFunds, effectively counting the hedgingFees twice. As a result, usedFunds is higher than it should be, available funds are lower, and the derived token price is artificially depressed. This mis‑calculation can be triggered on any trade that incurs hedging fees, which includes the typical openLong, closeLong, openShort and closeShort functions. An attacker could repeatedly open trades that generate hedging fees, inflating usedFunds and driving the pool token price below its fair value. Liquidity providers would then see a reduced token price, lower withdrawable balances, and may experience unexpected zero or reduced payouts when attempting to redeem their shares. The issue was uncovered during a Code4rena audit by comparing expected accounting values against on‑chain state; the test suite demonstrated that pool.totalFunds matched expectations while pool.usedFunds was consistently higher, leading to a token price that failed the expected‑price assertion. The bug is subtle because the totalFunds figure appears correct, masking the error unless the usedFunds or token price is explicitly inspected. To remediate, the contract must deduct hedgingFees from usedFunds at the point where tradeCost is subtracted, ensuring that the net margin requirement reflects the true fee burden. This adjustment restores accurate accounting, correct token pricing, and prevents potential price manipulation or loss of withdrawable funds.
