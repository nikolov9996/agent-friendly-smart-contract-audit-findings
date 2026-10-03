---
id: 25213
severity: "Medium"
---

# Withdraw and borrow can be DoSed in BaseRouter

## Description

Withdraw and borrow actions in the BaseRouter require the owner to increase the approval allowances. If the allowance increase and withdrawal action transaction are not done atomically (via a multicall, for example), anyone can withdraw 1 token, which will make the real withdraw action revert due to insufficient balance (borrowing is similar).

## Proof of Concept

No PoC provided.

## Recommendation

Similarly to the deposit(...) action _safePullTokenFrom(...), only the owner of the withdrawal and borrow actions should be able to call these actions directly. To allow someone withdrawing for a user or cross chain withdrawals, the withdrawal should only be allowed if there was a permit action before (same for borrowing).
