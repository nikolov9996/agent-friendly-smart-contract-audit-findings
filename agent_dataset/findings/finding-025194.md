---
id: 25194
severity: "Crit/High"
---

# ConnextHandler executeFailedWithUpdatedArgs(...) reentrancy allowedCaller can steal all ConnextHandler tokens

## Description

In executeFailedWithUpdatedArgs(...), the allowedCaller can steal all assets available on the ConnextHandler by calling executeFailedWithUpdatedArgs(...) again after the xBundle(...) call. This can be mitigated also by adding the nonReentrant modifier to xBundle(...).

## Proof of Concept

No PoC provided.

## Recommendation

Write txn.executed = true; before the try/catch call and rewrite txn.executed = false if it fails.
