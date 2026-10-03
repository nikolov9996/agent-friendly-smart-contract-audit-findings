---
id: 25269
severity: "Low/Info"
---

# KeyringCoreV2Base::registerKey() could check that validTo is equal to or bigger than block.timestamp

## Description

KeyringCoreV2Base::registerKey() registers a key with a validity between validFrom and validTo. It checks if validTo <= validFrom, but does not confirm that validTo is not set in the past.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
if (validTo < block.timestamp) {
    revert ErrInvalidKeyRegistration("IVT");
}
```
