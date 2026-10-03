---
id: 25204
severity: "Low/Info"
---

# When recording failed transactions in ConnextHandler, getting the next Nonce involves an unnecessary for loop

## Description

In ConnextHandler.sol, in order to record a failed transaction it is necessary to know the next nonce in the mapping, this involves a for cycle with a storage read that expends gas.

Since it only adds at the end of the list and access is always done using the nonce, the variable _failedTxns could be changed from a mapping of a mapping to the mapping of an array, this way in order to add a transaction push() could be used and to be able to know the nonce the length of the array would suffice.

This way the for cycle wouldn't be needed and it would save on gas.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
New declaration: mapping(bytes32 => FailedTxn[]) private _failedTxns;
Fetching the nonce: uint128 nextNonce = _failedTxns[transferId].length;
And adding to the list: _failedTxns[transferId].push(...);
```
