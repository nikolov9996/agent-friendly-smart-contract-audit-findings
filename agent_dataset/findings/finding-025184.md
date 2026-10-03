---
id: 25184
severity: "Crit/High"
---

# Changing providers might lead to lost assets in BorrowingVault and YieldVault

## Description

totalAssets(...) and totalDebt(...) are fetched from the set of providers, which can be changed. Thus, if providers change, but debt or assets are deposited/borrow from the old providers, totalAssets(...) and/or totalDebt(...) will change.

In the case of totalAssets(...), this means that users shares would be worth less, such that existing users would take a loss and new users could profit from depositing at this reduced rate and, after/if the totalAssets(...) were recovered, take a profit.

In the case of totalDebt(...), debtShares would be worth less, so existing users would make a profit by being able to payback their debt for less debt. New users would take a loss, following the same reasoning as before.

## Proof of Concept

No PoC provided.

## Recommendation

When removing a provider, check if the debt balance is bigger than 0, in which case, it should be repaid/moved to another provider first. In the case of the assets, ensuring that the deposit balance of a provider is 0 is vulnerable to a DoS attack, where attackers could deposit on the vault's behalf.

Thus, when changing providers, if the deposit balance of an old provider is not 0, these assets could be moved atomically to a new provider.
