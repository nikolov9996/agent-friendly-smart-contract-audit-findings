---
id: 25010
severity: "Crit/High"
---

# Borrower deposit, withdraw, deposit will reinit omniChainData.cdsPoolValue, getting profit stuck for cds depositors

## Description



## Proof of Concept

See above explanation.

## Impact

Cds depositor can not withdraw 50 USDa profit (and whole deposit, until someone else deposits cds and this user steals cds from the next depositor).

## Recommendation

Consider track if there is pending net cds pool.
