---
id: 20020
severity: "High"
---

# Possible to liquidate past the debt outstand-

## Description

It is possible to liquidate past the debt outstanding above the min borrow without liquidating the entire debt outstanding. Thus, leaving accounts with small debt that are not profitable to unwind if it needs to liquidate.

```solidity
if (depositUnderlyingInternal < maxLiquidatorDepositLocal) {
    // If liquidating past the debt outstanding above the min borrow, then the entire
    // debt outstanding must be liquidated.

    // (debtOutstanding - depositAmountUnderlying) is the post liquidation debt. As an
    // edge condition, when debt outstanding is discounted to present value, the account
    // may be liquidated to zero while their debt outstanding is still greater than the
    // min borrow size (which is normally enforced in notional terms -- i.e. non present
    // value). Resolving this would require additional complexity for not much gain. An
    // account within 20% of the minBorrowSize in a vault that has fCash discounting enabled
    // may experience a full liquidation as a result.
    require(
        h.debtOutstanding[currencyIndex].sub(depositUnderlyingInternal) < minBorrowSize,
        "Must Liquidate All Debt"
    );
}
```

• depositUnderlyingInternal represents the amount of underlying deposited by the liquidator  
• h.debtOutstanding[currencyIndex] is always a negative value representing debt outstanding of a specific currency in a vault account  
• minBorrowSize is always a positive value that represents the minimal borrow size of a specific currency (It is stored as uint32 in storage)

If liquidating past the debt outstanding above the min borrow, then the entire debt outstanding must be liquidated.

Assume the following scenario:  
• depositUnderlyingInternal = 70 USDC  
• h.debtOutstanding[currencyIndex] = -100 USDC  
• minBorrowSize = 50 USDC

If the liquidation is successful, the vault account should be left with -30 USDC debt outstanding because 70 USDC has been paid off by the liquidator. However, this should not happen under normal circumstances because the debt outstanding (-30) does not meet the minimal borrow size of 50 USDC and the liquidation should revert/fail.

The following piece of validation logic attempts to ensure that all outstanding debt is liquidated if post-liquidation debt does not meet the minimal borrowing size.

```solidity
require(
    h.debtOutstanding[currencyIndex].sub(depositUnderlyingInternal) < minBorrowSize,
    "Must Liquidate All Debt"
);
```

Plugging in the values from our scenario to verify if the code will revert if the debt outstanding does not meet the minimal borrow size.

```solidity
require(
    (-100 USDC - 70 USDC) < 50 USDC
);
// Results in:
require(
    (-170 USDC) < 50 USDC
);
// Which evaluates to true => no revert
```

The above shows that it is possible for someone to liquidate past the debt outstanding above the min borrow without liquidating the entire debt outstanding. This shows that the math formula in the code is incorrect and not working as intended.

A liquidation can bring an account below the minimum debt. Accounts smaller than the minimum debt are not profitable to unwind if it needs to liquidate.

As a result, liquidators are not incentivized to liquidate those undercollateralized positions. This might leave the protocol with bad debts, potentially leading to insolvency if the bad debts accumulate.

## Proof of Concept

no poc

## Recommendation

Update the formula as follows:

```solidity
require(
    h.debtOutstanding[currencyIndex].neg().sub(depositUnderlyingInternal) > minBorrowSize,
    "Must Liquidate All Debt"
);
```

Plugging in the values from our scenario again to verify if the code will revert if the debt outstanding does not meet the minimal borrow size.

```solidity
require(
    ((-100 USDC).neg() - 70 USDC) > 50 USDC
);
// Results in:
require(
    (100 USDC - 70 USDC) > 50 USDC
);
// Which evaluates to:
require(30 USDC > 50 USDC)
// => false => revert
```

The above will trigger a revert as expected when the debt outstanding does not meet the minimal borrow size.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect liquidation validation check that permits a liquidator to repay more than the outstanding debt and leave the borrower with a residual debt that is smaller than the protocol‑defined minimum borrow size. The root cause is that the contract stores debtOutstanding as a signed negative integer, but the require condition compares the raw signed value after subtraction directly against the unsigned minBorrowSize using a '<' operator. Because a negative number minus a positive deposit becomes an even larger negative number, the expression is always true, so the check never reverts when the post‑liquidation debt falls below the minimum. An attacker can trigger a liquidation where the liquidator supplies enough underlying to reduce the borrower’s debt below minBorrowSize, yet the transaction succeeds because the condition evaluates to true. The impact is that accounts can end up with a small, unprofitable debt that liquidators are not incentivized to unwind, leading to lingering bad debt and potential insolvency if many such positions accumulate. This occurs whenever a vault account is liquidated and the liquidator’s deposit amount exceeds the difference between the absolute debt and the minimum borrow threshold. The affected parties are borrowers whose positions remain under‑collateralized, liquidators who lose incentive, and the protocol which may suffer from unrecovered debt. The issue was discovered during a manual audit of the liquidation logic, where the auditor noticed that the mathematical inequality did not reflect the intended business rule. The bug is subtle because the code uses signed arithmetic and the condition appears syntactically correct, making it easy to overlook that the comparison is inverted. To fix the issue, the validation should compare the absolute remaining debt (or the negated debtOutstanding) after the liquidator’s deposit with minBorrowSize using a '>' check, ensuring that any post‑liquidation debt smaller than the minimum triggers a revert. In generic terms, this is a faulty boundary‑check bug in financial contract logic that allows a state transition that violates accounting assumptions, resulting in debt that should be considered fully liquidated remaining on‑chain.
