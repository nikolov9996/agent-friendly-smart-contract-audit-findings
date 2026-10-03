---
id: 25521
severity: "Low/Info"
---

# Missing disableInitializers() call in the constructor

## Description

When using Initializable.sol, it's a good practice calling disableInitializers() in the constructor, such that the implementation itself can't be initialized.

## Proof of Concept

No PoC provided.

## Recommendation

Use:

```solidity
constructor() {
    _disableInitializers();
}
```
