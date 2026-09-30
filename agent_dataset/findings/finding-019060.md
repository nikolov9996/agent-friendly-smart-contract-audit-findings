---
id: 19060
severity: "High"
---

# The amount of debt removed during `liquidation` may be worth more than the account’s collateral

## Description

```solidity
The contract decreases user’s debts but may not take the full worth in collateral from the user, leading to the contract losing potential funds from the missing collateral.
```

## Proof of Concept

```solidity
During the `liquidate()` function call, the function `_updateBorrowAndCollateralShare()` is eventually invoked. This function liquidates a user’s debt and collateral based on the value of the **collateral** they own.

In particular, the equivalent amount of debt, `availableBorrowPart` is calculated from the user’s collateral on line 225 through the `computeClosingFactor()` function call.

Then, an additional fee through the `liquidationBonusAmount` is applied to the debt, which is then compared to the user’s debt on line 240. The minimum of the two is assigned `borrowPart`, which intuitively means the maximum amount of debt that can be removed from the user’s debt.

`borrowPart` is then increased by a bonus through `liquidationMultiplier`, and then converted to generate `collateralShare`, which represents the amount of collateral equivalent in value to `borrowPart` (plus some fees and bonus).

This new `collateralShare` may be more than the collateral that the user owns. In that case, the `collateralShare` is simply decreased to the user’s collateral.

`collateralShare` is then removed from the user’s collateral.

The problem lies in that although the `collateralShare` is equivalent to the `borrowPart`, or the debt removed from the user’s account, it could be worth more than the collateral that the user owns in the first place. Hence, the contract loses out on funds, as debt is removed for less than it is actually worth.

To demonstrate, we provide a runnable POC.

    Collateral amt:  BigNumber { value: "10000000000000000000000" }
    WBTC borrow val:  BigNumber { value: "74000000" }
    [$] Original price:  BigNumber { value: "10000" }
    Price Drop: 120%
    Running liquidation... 
    [*] Reverted with reason: collateralShare and borrowPart not worth the same [Bug]
          ✔ POC (2289ms)

As demonstrated, the function call reverts due to the `require` statement added in the preconditions.
```

## Recommendation

```solidity
One potential mitigation for this issue would be to calculate the `borrowPart` depending on the existing users’ collateral factoring in the fees and bonuses. The `collateralShare` with the fees and bonuses should not exceed the user’s collateral.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the liquidation routine of the lending contract, where the amount of debt that can be erased (borrowPart) is converted into a collateral share that is taken from the borrower. The conversion adds liquidation fees and a bonus multiplier, but the code does not enforce that the resulting collateralShare is bounded by the borrower’s actual collateral balance. Consequently, when market prices move sharply and the computeClosingFactor function yields a large borrowPart, the added fees and bonus can inflate the collateralShare so that it represents a value greater than the borrower’s total collateral. The contract then simply caps the collateralShare to the borrower’s balance, removes that amount of collateral, and records the larger borrowPart as repaid debt. This mismatch means the protocol removes more debt than the value of collateral actually taken, effectively allowing debt to disappear without an equivalent loss of assets. An attacker can trigger liquidation on an under‑collateralised position, causing the protocol to write‑off debt while only seizing a fraction of the required collateral, leading to a net loss of funds for the protocol and its lenders. The issue manifests when a price drop or aggressive liquidation parameters cause the closing factor to produce a borrowPart that, after fees and bonuses, exceeds the borrower’s collateral. All participants who rely on the accounting invariants of the protocol—borrowers, lenders, and the protocol treasury—are affected because the accounting guarantees are broken. The flaw was discovered during a Code4rena audit through a crafted proof‑of‑concept that simulated a 120 % price drop and observed a revert triggered by a require statement checking that collateralShare and borrowPart have equal worth. The problem is subtle because the liquidation flow appears to take collateral from the user, yet the invariant that debt removed equals collateral taken is silently violated, making it easy to miss in manual review. To remediate, the calculation of borrowPart must be constrained so that the resulting collateralShare, after applying fees and bonuses, never exceeds the borrower’s actual collateral. In practice this means recomputing borrowPart based on the available collateral, incorporating fees and bonuses into the bound, and adding explicit checks that enforce collateralShare ≤ userCollateral before proceeding with the liquidation. This restores the intended accounting relationship where the value of debt erased matches the value of collateral seized, preventing the protocol from losing funds.
