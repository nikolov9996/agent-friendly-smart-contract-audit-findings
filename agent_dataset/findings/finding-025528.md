---
id: 25528
severity: "Low/Info"
---

# Implement Storage Gap in Delegatable Contract

## Description

If additional variables are added to the Delegatable contract, conflicts may arise with the storage slots previously written on the proxy.

## Proof of Concept

No PoC provided.

## Recommendation

To mitigate this issue, insert a storage gap in the contract:

```solidity
abstract contract Delegatable is IDelegatable {
    mapping(address => address) public delegations;
    address private senderOverride;
    @>
    uint256[49] __gap;
    // *** code ***
```
