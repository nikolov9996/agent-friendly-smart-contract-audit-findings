---
id: 25321
severity: "Low/Info"
---

# In MapleLoanFactory, isLoan has the same functionality of isInstance and thus can be removed.

## Description

The mapping isLoan is only modified in the respective MapleLoanFactory.sol contract which extends MapleProxyFactory.sol. isLoan is only modified in line 24 of MapleLoanFactory where, in the same call, isInstance is also set to true in line 95 of MapleProxyFactory.

So every valid loan according to isLoan is a valid instance according to isInstance and every address that is not registered in isLoan will also not be registered in isInstance.

## Proof of Concept

No PoC provided.

## Recommendation

The mapping isLoan can be removed and isInstance can be used in its place whenever needed.
