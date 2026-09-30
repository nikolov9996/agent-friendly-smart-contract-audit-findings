---
id: 19076
severity: "High"
---

# Overflow risk in Market contract

## Description

Actions of users (borrow, repay, removeCollateral, …) in Martket contract might be reverted by overflow, resulting in their funds might be frozen.

## Proof of Concept

Function `_isSolvent` in `Market` contract use conversion from share to amount of yieldBox.

```solidity
yieldBox.toAmount(
    collateralId,
    collateralShare *
        (EXCHANGE_RATE_PRECISION / FEE_PRECISION) *
        collateralizationRate,
    false
)
```

It will trigger `_toAmount` function in `YieldBoxRebase` contract

```solidity
function _toAmount(
    uint256 share,
    uint256 totalShares_,
    uint256 totalAmount,
    bool roundUp
) internal pure returns (uint256 amount) {
    totalAmount++;
    totalShares_ += 1e8;

    amount = (share * totalAmount) / totalShares_;

    if (roundUp && (amount * totalShares_) / totalAmount < share) {
        amount++;
    }
}
```

The calculation `amount = (share * totalAmount) / totalShares_` might be overflow because `share * totalAmount` = `collateralShare * (EXCHANGE_RATE_PRECISION / FEE_PRECISION) * collateralizationRate * totalAmount`

In the default condition,  
`EXCHANGE_RATE_PRECISION` = 1e18,  
`FEE_PRECISION` = 1e5,  
`collateralizationRate` = 0.75e18

The `collateralShare` is equal to around `1e8 * collateralAmount` by default (because `totalAmount++; totalShares_ += 1e8;` is present in the `_toAmount` function).

=> **`share * totalAmount` ~= (collateralAmount * 1e8) * (1e18 / 1e5) * 0.75e18 * totalAmount = collateralAmount * totalAmount * 0.75e39**

This formula will overflow when `collateralAmount * totalAmount` > 1.5e38. This situation can occur easily with 18-decimal collateral. As a consequence, user transactions will revert due to overflow, resulting in the freezing of market functionalities.

The same issue applies to the calculation of `_computeMaxBorrowableAmount` in the Market contract.

## Recommendation

Reduce some variables used to trigger yieldBox.toAmount(), such as `EXCHANGE_RATE_PRECISION` and `collateralizationRate`, and use these variables to calculate with the obtained amount. Example, the expected amount can be calculated as:

```solidity
yieldBox.toAmount(
    collateralId,
    collateralShare,
    false
) * (EXCHANGE_RATE_PRECISION / FEE_PRECISION) * collateralizationRate
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

An arithmetic overflow occurs in the Market contract when it converts a collateral share value to a token amount using the YieldBox.toAmount function. The conversion multiplies the user‑provided collateralShare by several large scaling constants – EXCHANGE_RATE_PRECISION (1e18), the ratio EXCHANGE_RATE_PRECISION / FEE_PRECISION (1e13), and collateralizationRate (≈0.75e18) – and then by the totalAmount stored in YieldBox. Because YieldBox’s internal _toAmount routine adds 1 to totalAmount and 1e8 to totalShares_ before performing the multiplication share * totalAmount, the intermediate product can exceed the 256‑bit limit when collateralAmount and totalAmount are moderately large (for example, when collateralAmount * totalAmount > 1.5e38). Solidity versions prior to built‑in overflow checks or code that uses unchecked arithmetic will allow this multiplication to wrap, causing the function to revert with an overflow error. The overflow is triggered during calls to _isSolvent and _computeMaxBorrowableAmount, which are executed on every user action such as borrow, repay, or removeCollateral. When the overflow happens, the transaction reverts, no state changes are applied, and the user’s funds remain locked in the contract, giving the appearance that the market has “frozen”. From a user’s perspective the UI shows a failed transaction, often with a generic “overflow” or “reverted” message, while the displayed balances do not change – the user expects to receive a loan or to withdraw collateral but receives nothing. The bug belongs to the class of unchecked arithmetic overflow vulnerabilities that break accounting assumptions: the protocol assumes that the conversion from share to amount is monotonic and safe, but the overflow breaks that invariant and prevents correct loan‑to‑collateral calculations. The issue was discovered during a formal audit by Code4rena, where the auditors traced the conversion logic, calculated the worst‑case product, and identified that typical 18‑decimal collateral values can easily reach the overflow threshold. The problem is hard to notice in normal testing because the overflow only manifests with large collateral or totalAmount values, which are rarely exercised in unit tests. The recommended mitigation is to reduce the magnitude of the scaling constants before multiplication, for example by applying the division EXCHANGE_RATE_PRECISION / FEE_PRECISION and the collateralizationRate after the toAmount call, or by performing the multiplication in a checked context, using smaller intermediate types, or redesigning the accounting formula to avoid a single large product. By scaling down the inputs or rearranging the order of operations, the intermediate value stays within the 256‑bit range, restoring correct solvency checks and allowing borrow, repay, and collateral removal to succeed without freezing user funds.
