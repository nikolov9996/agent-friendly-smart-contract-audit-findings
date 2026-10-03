---
id: 25386
severity: "Low/Info"
---

# Unused parameters names can be removed to ignore compiler warnings

## Description

[lzReceive()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L119-L125>) only uses the payload parameter, so the other names can be removed, leaving only the types: function _lzReceive( Origin calldata, // struct containing info about the message sender

```solidity
bytes32, // global packet identifier
bytes calldata payload, // encoded message payload being received
```

address, // the Executor address. bytes calldata // arbitrary data appended by the Executor

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
