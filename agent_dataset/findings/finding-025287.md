---
id: 25287
severity: "Low/Info"
---

# Function cancelMint can be frontrunned to grief a validator

## Description

In the [MinterGateway.cancelMint](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MinterGateway.sol#L327-L335>) function, an approved validator cancels a mint proposal by passing the minter address and mintId. The function will revert if the the minter's proposal doesn't correspond to the input id.

Each mintId is generated from a nonce, and this is independent from the proposal details. A minter can frontrun any cancelMint call by calling proposeMint with the exact same parameters as their mint proposal that was about to be cancelled. This will revert the validator's transaction, because the specified id will no longer be correct.

A minter can keep doing this until they potentially get frozen by the validator.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
