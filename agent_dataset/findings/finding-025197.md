---
id: 25197
severity: "Low/Info"
---

# Borrowing is not vulnerable to an inflation attack, it's unnecessary to borrow when initializing the vault

## Description

An inflation attack occurs because attackers manipulate the denominator of the assets calculation by increasing totalAssets(...), which when calculating the shares as shares = assets * supply / totalAssets(...), would make it round down and the depositing user is stolen.

In the case of debt, it's not possible to increase the denominator totalDebt(...) without borrowing, which increases the shares. In fact, if the debtShares were rounded down by attackers, it would be beneficial to the user, who would have to pay less debt for the same debtShares.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the borrow line in the initializeVault(...).
