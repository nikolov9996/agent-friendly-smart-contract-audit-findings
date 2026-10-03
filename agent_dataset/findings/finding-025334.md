---
id: 25334
severity: "Medium"
---

# A pool delegate should not be allowed to be a borrower

## Description

A Pool Delegate should not be allowed to be a borrower otherwise they can leave with the funds at any time with no questions asked. We believe this is not the intended behavior, but currently the code allows it to happen (which means it could happen by mistake, for example by copy pasting the wrong address).

## Proof of Concept

No PoC provided.

## Recommendation

Suggestions to mitigate this issue (to implement in maple globals):

- In setValidBorrower, check if the address is a pool delegate.
- In setValidPoolDelegate, check if the address is a borrower.
