---
id: 25023
severity: "Crit/High"
---

# Type 1 borrower liquidation will incorrectly add cds profit directly to totalCdsDepositedAmount

## Description



## Proof of Concept

Consider a borrower that deposited 1 ETH at a 1000 USD / ETH price and borrowed 800 USDa. There is 1 cds depositor that deposited 1000 USDa. The price drops 20% and `borrowLiquidation::liquidationType1()` is called.

- `returnToAbond` is `(1000 - 800) * 10 / 100 = 20`.
- `cdsProfits` is `1000 - 800 - 20 = 180`.
- `liquidationAmountNeeded` is `800 + 20 = 820`.
- `cdsAmountToGetFromThisChain` is `820 - 180 = 640`.
- `omniChainData.totalCdsDepositedAmount` is `1000 - (820 - 180) = 360`. Now, every cumulative value or option fee is calculated as if there were 360 USDa deposited as cds depositors, but this is not true, as 820 cds will be liquidated and only 180 is left. The profit should be accounted for, but not in this variable.

## Impact

Cumulative value calculations and option fees will be incorrect, as they are divided by a bigger number of cds deposited (which was added the profit), but each cds depositor only has the same deposited amount to multiply by these rates.

## Recommendation

Do not add the profit to `totalCdsDepositedAmount`.
