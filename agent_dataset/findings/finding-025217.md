---
id: 25217
severity: "Crit/High"
---

# User fund loss due to depositing before unearn()

## Description



## Proof of Concept

## Vulnerability Detail

Suppose 1000 assets and 1000 shares that some user deposited. Now, 100 interest accrues and assets become 1100. Then, another user deposits 1000, getting `1000  1000 / 1100 = 909.09`* shares. Now, admin earns 1100, getting 1100 assets, where 100 are profit. Then, admin calls `PreDepositVault::claimProfit()`, transferring 100 profit to themselves. In the end, there are 2000 assets and 1909.09 shares. User 2 has assets equal to `909.09 `*` 2000 / 1909.09 = 952.38`, losing around 48 assets.

## Impact

Fund loss for users.

## Code Snippet

[https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdUSDC.sol#L62-L81](<https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdUSDC.sol#L62-L81>)

## Recommendation

Total assets shouldn't instantly decrease. One fix option is storing the last registered balanced, compare with the current aToken + asset balance, and the difference at each time is the interest. This way, this interest can all go to the admin or take a percentage of it. If it all goes to the admin, it doesn't make much sense to use ERC4626 because the price of each share will always remain the same.
