---
id: 25619
severity: "Low/Info"
---

# StakingOperator does not set isUnlockWindowActive to true in the constructor if the flag passed is true

## Description

The constructor of StakingOperator is

```solidity
constructor( uint256 unlockWindowStart, uint256 unlockWindowDuration, bool isUnlockWindowActive_, address owner ) Ownable(owner) {
    if (isUnlockWindowActive_) {
        _setUnlockWindow(unlockWindowStart, unlockWindowDuration);
    }
}
```

As can be seen, it receives a flag isUnlockWindowActive_, but never states the state variable isUnlockWindowActive. This may be intended, but flagging it because it is not clear.

## Proof of Concept

No PoC provided.

## Recommendation

Either place a comment or fix the issue.
