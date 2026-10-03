---
id: 25335
severity: "Low/Info"
---

# pool-v2-private: cache list length in memory and uncheck i_ to save gas.

## Description

In the PoolManager contract, function setIsLoanManager(): variable loanManagerList.length could be held in memory preventing multiple storage reads during the for loop. The ++i could also be unchecked for additional gas savings.

## Proof of Concept

No PoC provided.

## Recommendation

Cache the array length and uncheck the ++i. This function could also receive a hint with the index of the loan manager in the loanManagerList, preventing the for loop that iterates through the list, resulting in additional gas savings.
