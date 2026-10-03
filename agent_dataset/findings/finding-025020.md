---
id: 25020
severity: "Crit/High"
---

# Borrowing::redeemYields debits ABOND from msg.sender but redeems to user using ABOND.State data from user

## Description



## Proof of Concept

None

## Impact

- The ETH deposited in the external protocol that backs `ABOND` can be completely drained.
- `ABOND` value will fall to zero as there won't be ETH to redeem it for.

## Recommendation

Enforce `msg.sender` to be equal to `user`.
