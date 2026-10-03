---
id: 25423
severity: "Low/Info"
---

# RedeemQueue::get() reverts due to underflow when it should revert and throw the correct error

## Description

RedeemQueue::get() reverts due to underflow if index_.count == 0 instead of the error IndexOutOfRange.

## Proof of Concept

No PoC provided.

## Recommendation

IndexOutOfRange(index._offset, index._count, idx);
