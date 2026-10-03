---
id: 25296
severity: "Low/Info"
---

# StartedEarning event is emitted even if account is already earning

## Description

In [MToken._startEarning](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MToken.sol#L239C5-L239C56>) the StartedEarning event will be emitted even if the calling account is already earning:

```solidity
function _startEarning(address account_) internal {
    emit StartedEarning(account_);
    MBalance storage mBalance_ = _balances[account_];
    if (mBalance_.isEarning) return;
    // ... }
```

The same happens in the [MToken._stopEarning](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MToken.sol#L271>). The StoppedEarning event will be emitted even if the user isn't an earner.

## Proof of Concept

No PoC provided.

## Recommendation

Move the line that emits the event to the end of the function so that it will only fire when a new user starts/stops being an earner.
