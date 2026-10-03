---
id: 25013
severity: "Crit/High"
---

# totalCdsDepositedAmountWithOptionFees is incorrectly reduced in CDSLib::withdrawUser(), leading to stuck option fees

## Description



## Proof of Concept

See above.

## Impact

As `totalCdsDepositedAmountWithOptionFees` is 50, but the global `totalCdsDepositedAmountWithOptionFees` is null (it was correctly decreased), it will lead to incorrect calculations when getting the option fees [proportions](<https://github.com/sherlock-audit/2024-11-autonomint/blob/main/Blockchain/Blockchian/contracts/lib/CDSLib.sol#L62>). For example, if someone deposits 1000 cds and another user deposits borrows (suppose it pays more 50 USD), it will add option fees on deposit. Then, when the borrower withdraws and the cds depositor withdraws, `getOptionsFeesProportions()` will calculate `totalOptionFeesInOtherChain` as `1050 - 1100`, which underflows.

## Recommendation

The correct code is:

```solidity
totalCdsDepositedAmountWithOptionFees -= (params.cdsDepositDetails.depositedAmount - params.cdsDepositDetails.liquidationAmount + (params.optionFees - params.optionsFeesToGetFromOtherChain));
```
