---
id: 25053
severity: "Medium"
---

# fyToken contribution limits are incorrect as they compare fyToken and buyToken amounts with idoSize in idoToken units

## Description

The `fyToken` contribution limit is enforced as:

```solidity
uint256 globalTotalFunded = idoConfig.totalFunded[buyToken] + idoConfig.totalFunded[fyToken] + amount;
...
uint256 maxFyTokenFunding = (idoConfig.idoSize * idoConfig.fyTokenMaxBasisPoints) / 10000;
if (globalTotalFunded > maxFyTokenFunding) revert FyTokenContributionExceedsLimit();
```

As can be seen, `maxFyTokenFunding` is in `idoToken` units (`idoSize` refers to `idoToken`) and `globalTotalFunded` in `fyToken` or `buyToken` units.

## Proof of Concept

No PoC provided.

## Recommendation

Make sure the limit is imposed by comparing the same units.
