---
id: 25268
severity: "Low/Info"
---

# Admin checks in KeyringCoreV2Base could be placed in a modifier to increase readability and reduce code duplication

## Description

Usually access control is performed in modifiers, as is the case with onlyOwner, for example. The same could be applied to the admin check in each permissioned function to increase readability and decrease code duplication.

## Proof of Concept

No PoC provided.

## Recommendation

Create a modifier and implement the body of a function to reduce deployment costs (modifier's code is duplicated into each function which increases deployment costs significantly).

```solidity
modifier onlyAdmin() {
    _onlyAdmin();
    _;
}
function _onlyAdmin() internal {
    if (msg.sender != _admin) {
        revert ErrCallerNotAdmin(msg.sender);
    }
}
```
