---
id: 25081
severity: "Medium"
---

# StrategyRouterLib.sol bug when subtracting from balance

## Description

[Lines 665 and 666](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouterLib.sol#L666>) of the StrategyRouterLib have the following code: currentTokenDatas[j].currentBalance -= desiredAllocationUniform; currentTokenDatas[j].currentBalanceUniform -= desiredAllocationUniform; // not actually in uniform format Here, variable desiredAllocationUniform actually holds the original desired allocation value (not in the uniform format), so in line 666 the subtraction is being performed by variables in different formats.

Depending on the difference between the original and the uniform decimals, one of the three scenarios should happen:

- if the number of decimals in the same, the code should run without a problem
- if the number of original decimals is higher than the number of uniform decimals, the execution will most likely underflow and revert in line 666.
- if the number of original decimals is smaller than the number of uniform decimals, the contract will try to transfer tokens it does not have and revert.
- no under/overflow happens but the accounting becomes incorrect.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
Change line 666 to currentTokenDatas[j].currentBalanceUniform -= toUniform(desiredAllocationUniform, supportedTokensWithPrices[j].token);
```
