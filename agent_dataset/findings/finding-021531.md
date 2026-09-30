---
id: 21531
severity: "High"
---

# When `sellCreditMarket`

## Description

The protocol might receive a lower fee than expected when `sellCreditMarket()` is called to sell credit for a specific cash amount.

## Proof of Concept

The protocol allows a user to sell their `credit` for `szaUSDC`, which can be used to redeem USDC thereafter.

* If a specific amount of `credit` is sold for `szaUSDC`, `sellCreditMarket()` will calculate the amount of `szaUSDC` received and `fees` paid to `feeReceipient`.
* If `credit` is sold for a specific amount of `szaUSDC`, `sellCreditMarket()` will calculate the amount of `credit` sold and `fees` paid to `feeReceipient`.

The calculation should follow the below rules:

Note: please see the calculation scenarios in warden’s[original submission](https://github.com/code-423n4/2024-06-size-findings/issues/288).

We can verify [the fee samples](https://docs.size.credit/technical-docs/contracts/2.3-fees) with the above formulas.

**Example 1** : Bob owned 120 `credit` and sell 120 `credit` to Candy for `szaUSDC`. All results of the calculation are same as [Example 1](https://docs.size.credit/technical-docs/contracts/2.3-fees).

**Example 2** : Bob owned 120 `credit` and sell `credit` to Candy for 50 `szaUSDC`. However, the swap fee stated in [Example 2](https://docs.size.credit/technical-docs/contracts/2.3-fees) is 0.5, which is different with the result calculated from in the formulas.

The sold credit and swap fee are calculated in [`getCreditAmountIn()`](https://github.com/code-423n4/2024-06-size/blob/main/src/libraries/AccountingLibrary.sol#L253-L256):
    
253:            creditAmountIn = Math.mulDivUp(
254:                cashAmountOut + state.feeConfig.fragmentationFee, PERCENT + ratePerTenor, PERCENT - swapFeePercent
255:            );
256:            fees = Math.mulDivUp(cashAmountOut, swapFeePercent, PERCENT) + state.feeConfig.fragmentationFee;

As we can see, the calculation of `creditAmountIn` is same as the calculation of `credit_{sold} (4)`; however, the swap fee is different. This leaves the protocol suffering a loss on swap fees when `sellCreditMarket()` is called to sell credit for a specific cash amount.

Copy the below codes to [SellCreditMarketTest.t.sol](https://github.com/code-423n4/2024-06-size/blob/main/test/local/actions/SellCreditMarket.t.sol) and run `forge test --match-test test_SellCreditMarket_sellCreditMarket_incorrectFee`:
    
```solidity
function test_SellCreditMarket_sellCreditMarket_incorrectFee() public {
    _deposit(bob, weth, 100e18);
    _deposit(alice, usdc, 100e6);
    _buyCreditLimit(alice, block.timestamp + 365 days, YieldCurveHelper.pointCurve(365 days, 0.2e18));
    uint256 tenor = 365 days;
    vm.startPrank(bob);
    uint256 apr = size.getLoanOfferAPR(alice, tenor);
    // @audit-info alice has 100e6 szaUSDC 
    assertEq(size.getUserView(alice).borrowATokenBalance, 100e6);
    uint256 snapshot = vm.snapshot();
    // @audit-info bob sell 120e6 credit to alice for szaUSDC
    size.sellCreditMarket(
        SellCreditMarketParams({
            lender: alice,
            creditPositionId: RESERVED_ID,
            amount: 120e6,
            tenor: tenor,
            deadline: block.timestamp,
            maxAPR: apr,
            exactAmountIn: true
        })
    );
    // @audit-info alice has 0 szaUSDC left
    assertEq(size.getUserView(alice).borrowATokenBalance, 0);
    // @audit-info bob received 99.5e6 szaUSDC
    assertEq(size.getUserView(bob).borrowATokenBalance, 99.5e6);
    // @audit-info bob owed 120e6 debt
    assertEq(size.getUserView(bob).debtBalance, 120e6);
    // @audit-info feeRecipient received 0.5e6 szaUSDC as fee
    assertEq(size.getUserView(feeRecipient).borrowATokenBalance, 500000);
    // @audit-info restore to the snapshot before sellCreditMarket
    vm.revertTo(snapshot);
    // @audit-info bob sell credit to alice for 99.5e6 szaUSDC 
    size.sellCreditMarket(
        SellCreditMarketParams({
            lender: alice,
            creditPositionId: RESERVED_ID,
            amount: 99.5e6,
            tenor: tenor,
            deadline: block.timestamp,
            maxAPR: apr,
            exactAmountIn: false
        })
    );
    // @audit-info alice has 2500 szaUSDC left
    assertEq(size.getUserView(alice).borrowATokenBalance, 2500);
    // @audit-info bob received 99.5e6 szaUSDC
    assertEq(size.getUserView(bob).borrowATokenBalance, 99.5e6);
    // @audit-info bob owed 120e6 debt
    assertEq(size.getUserView(bob).debtBalance, 120e6);
    // @audit-info feeRecipient received 497500 szaUSDC as fee
    assertEq(size.getUserView(feeRecipient).borrowATokenBalance, 497500);
}
```

## Recommendation

Correct the swap fee calculation:
    
```solidity
function getCreditAmountIn(
    State storage state,
    uint256 cashAmountOut,
    uint256 maxCashAmountOut,
    uint256 maxCredit,
    uint256 ratePerTenor,
    uint256 tenor
) internal view returns (uint256 creditAmountIn, uint256 fees) {
    uint256 swapFeePercent = getSwapFeePercent(state, tenor);

    uint256 maxCashAmountOutFragmentation = 0;

    if (maxCashAmountOut >= state.feeConfig.fragmentationFee) {
        maxCashAmountOutFragmentation = maxCashAmountOut - state.feeConfig.fragmentationFee;
    }

    // slither-disable-next-line incorrect-equality
    if (cashAmountOut == maxCashAmountOut) {
        // no credit fractionalization

        creditAmountIn = maxCredit;
        // -           fees = Math.mulDivUp(cashAmountOut, swapFeePercent, PERCENT);
        // +           fees = Math.mulDivUp(cashAmountOut, swapFeePercent, PERCENT - swapFeePercent);
        fees = Math.mulDivUp(cashAmountOut, swapFeePercent, PERCENT - swapFeePercent);
    } else if (cashAmountOut < maxCashAmountOutFragmentation) {
        // credit fractionalization

        creditAmountIn = Math.mulDivUp(
            cashAmountOut + state.feeConfig.fragmentationFee, PERCENT + ratePerTenor, PERCENT - swapFeePercent
        );
        // -            fees = Math.mulDivUp(cashAmountOut, swapFeePercent, PERCENT) + state.feeConfig.fragmentationFee;
        // +            fees = Math.mulDivUp(cashAmountOut + state.feeConfig.fragmentationFee, swapFeePercent, PERCENT - swapFeePercent) + state.feeConfig.fragmentationFee;
        fees = Math.mulDivUp(cashAmountOut + state.feeConfig.fragmentationFee, swapFeePercent, PERCENT - swapFeePercent) + state.feeConfig.fragmentationFee;
    } else {
        // for maxCashAmountOutFragmentation < amountOut < maxCashAmountOut we are in an inconsistent situation
        //   where charging the swap fee would require to sell a credit that exceeds the max possible credit

        revert Errors.NOT_ENOUGH_CASH(maxCashAmountOutFragmentation, cashAmountOut);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the fee calculation performed by the accounting library when the sellCreditMarket function is used to sell credit for a specific amount of cash (szaUSDC). The contract computes the swap fee with the expression Math.mulDivUp(cashAmountOut, swapFeePercent, PERCENT) in the original code, but the correct economic model requires the fee to be calculated on the net amount after the fee is taken, i.e. cashAmountOut * swapFeePercent / (PERCENT‑swapFeePercent). By using the plain denominator PERCENT the contract under‑charges the fee, especially in the branch where the caller requests an exact cash amount (exactAmountIn=true). The root cause is an arithmetic mistake: the denominator does not account for the fee being taken out of the cash amount, leading to a lower fee than the protocol’s specification. An attacker can exploit this by invoking sellCreditMarket with exactAmountIn set to true and specifying a cash amount that triggers the faulty branch. The contract will then credit the seller with more cash than it should, while the feeRecipient receives a smaller fee than documented. The impact is a loss of revenue for the protocol: each affected trade yields a fee shortfall that accumulates over many transactions, reducing the funds available to the feeRecipient and potentially destabilising the economic incentives of the system. The bug manifests only when the function is called to sell credit for a predetermined cash amount, either in the no‑fractionalisation case (cashAmountOut equals maxCashAmountOut) or when cashAmountOut is below the fragmentation‑adjusted maximum. Users of the protocol – lenders, borrowers and the feeRecipient – are affected because balances may not match the expected accounting rules; a user may notice that they receive slightly more cash than anticipated while the fee shown on‑chain is lower than the protocol’s fee table. The issue was discovered during a formal audit when the auditors compared on‑chain fee outcomes with the fee tables published in the protocol documentation and observed a discrepancy in Example 2. It is hard to notice because the deviation is small (often a few hundred thousand units on a million‑scale transaction) and the UI typically displays only the net cash received, not the detailed fee breakdown. To remediate, the fee formula should be corrected to use the denominator (PERCENT‑swapFeePercent) and to incorporate the fragmentation fee consistently in both the credit amount and fee calculations. This class of bug belongs to arithmetic or rounding errors in fee logic, where an incorrect denominator leads to under‑charging. The failure mode can be described as “funds disappear from the fee pool” or “refund calculation error” because the protocol pays out more cash than it should while collecting insufficient fees, violating the intended accounting invariants.
