---
id: 25271
severity: "Low/Info"
---

# No need to set isActive to false if that mapping entry was deleted

## Description

In [MinterGateway.deactivateMinter](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MinterGateway.sol#L357>) the minter's entry in _minterStates is deleted using the

```solidity
delete keyword: function deactivateMinter(address minter_) external
onlyActiveMinter(minter_) returns (uint240 inactiveOwedM_) {
    // ... delete _minterStates[minter_];
    delete _mintProposals[minter_];
    _minterStates[minter_].isDeactivated = true;
    _minterStates[minter_].isActive = false;
    // ... }
```

This action sets all types of that specific entry to its default value, and so, there is no need to set isActive to false as this is the default value set by the delete keyword.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the following line from deactivateMinter function: _minterStates[minter_].isActive = false;
