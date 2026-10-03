---
id: 25195
severity: "Low/Info"
---

# Handling someone else repaying debt for the BorrowingVault could be done differently

## Description

In _convertDebtToShares(...), if totalDebt(...) is 0, it reverts. This means that, if someone decides to repay the full vault debt, this function would always revert. The current measure taken is pausing the vault and then borrowing a debt amount equal to the debt shares.

This leads to a temporary halting of the vault and it may require rebalancing the providers to enable borrowing all the debt from the same provider (if the debt was distributed among many providers).

## Proof of Concept

No PoC provided.

## Recommendation

The Openzeppelin ERC4626 implementation, instead of placing totalAssets(...) in the denominator (here equivalent to totalDebt(...)), places totalAssets(...) + 1 (also adds 1 when converting shares to assets). The yield vault could also use this logic, although I don't think it's possible for the totalAssets(...) to be 0 and the shares different from 0.

This would fix this problem, take a look at the following example There are 10000 shares and 10000 assets. User repays 10000 assets (directly at provider(s)), and now the supply is 10000 and totalDebt is 0.

Some user wants to borrow 100 debt: shares = debt * supply / (totalAssets + 1) = 100 * 10_000 / 1 = 1_000_000 if this user tries to pay back the debt debt = shares * (totalAssets + 1) / supply = 1_000_000 * 101 / 1_010_000 = 100 which adds up correctly if another user wants to repay their debt, the calculation would be shares = 100, supply = 10000, assets = 0 debt = shares * (totalAssets + 1) / supply = 100 * 1 / 10000 = 0 which means their debt would have been paid by the attacker.

It would only increase if they borrow more, which would work correctly, as shown in the previous example.
