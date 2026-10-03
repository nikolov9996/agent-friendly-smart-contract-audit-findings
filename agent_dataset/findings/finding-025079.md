---
id: 25079
severity: "Medium"
---

# Halted withdrawals in BatchOut:withdrawFulfill() due to tokens transfer() reverting on 0 transfer amount

## Description

Some tokens may [revert](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/Batch.sol#L214>) on 0 amount transfers. This means that if someone schedules a withdrawal of 1 share, it could convert to a 0 amount and [halt](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/BatchOut.sol#L379>) all the other withdrawals.

## Proof of Concept

No PoC provided.

## Recommendation

Skip the transfer if the amount to transfer is 0.
