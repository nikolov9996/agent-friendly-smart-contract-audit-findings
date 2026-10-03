---
id: 25261
severity: "Low/Info"
---

# KeyringCoreV2Base::_createCredential() could use currentTime instead of block.timestamp on the creatBefore check

## Description

KeyringCoreV2Base::_createCredential() checks that the current block.timestamp has not exceeded creatBefore by doing:

```solidity
if (block.timestamp > creatBefore) {
    revert ErrInvalidCredential(policyId, tradingAddress, "EPO");
}
```

It could use currentTime instead as it has been cached.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
if (currentTime > creatBefore) {
    revert ErrInvalidCredential(policyId, tradingAddress, "EPO");
}
```
