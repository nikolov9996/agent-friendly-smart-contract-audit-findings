---
id: 25292
severity: "Low/Info"
---

# Unnecessary Recomputation of Storage Pointer in MToken._startEarning

## Description

In [MToken._startEarning](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MToken.sol#L239>) function, the _balances mapping is stored in the mBalance_ variable.

MBalance storage mBalance_ = _balances[account_]; But a few lines below, instead of using mBalance_ to retrieve rawBalance, _balances[account].rawBalance is used again spending unnecessary gas.

```solidity
function _startEarning(address account_) internal {
    emit StartedEarning(account_);
    MBalance storage mBalance_ = _balances[account_];
    if (mBalance_.isEarning) return;
    mBalance_.isEarning = true;
    // Treat the raw balance as present amount for non earner. uint240 amount_ = _balances[account_].rawBalance;
```

## Proof of Concept

No PoC provided.

## Recommendation

Change the amount_ variable to: uint240 amount_ = mBalance_.rawBalance;
