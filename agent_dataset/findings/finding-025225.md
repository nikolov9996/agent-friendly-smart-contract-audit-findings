---
id: 25225
severity: "Low/Info"
---

# In glAVAX, checking that amount > 0 earlier can save some gas

## Description

In the function withdraw() the function _borrowLiquidity() is called to borrow funds from the lending pool if necessary. _borrowLiquidity() eventually calls _lendAvax() that checks the following conditions if (amount > 0 && lendingBalance > 0).

The condition amount > 0 could be checked instead in the withdraw() function before calling _borrowLiquity(), this would make it so that when amount == 0 no gas is spent going into the function _borrowLiquidity().

## Proof of Concept

No PoC provided.

## Recommendation

Put check before calling _borrowLiquidity():

```solidity
if( avaxAmount > 0) {
    avaxAmount = _borrowLiquidity(avaxAmount);
}
And remove check in _lendAvax(): if (lendingBalance > 0) {
```
