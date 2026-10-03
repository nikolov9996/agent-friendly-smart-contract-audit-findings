---
id: 25342
severity: "Low/Info"
---

# Throughout code base: use Solidity native errors implementation instead of string errors.

## Description

Solidity allows for their implementation [of native custom errors](<https://blog.soliditylang.org/2021/04/21/custom-errors/>) that is more gas-efficient than using a string within the require function to explain to the user where the call reverted (the way it's implemented in the Maple Protocol right now).

We understand that string errors might be used to give more information on where the call reverted; however, this information can still be passed to the user by having specifically named errors.

## Proof of Concept

No PoC provided.

## Recommendation

Use custom errors, for example, use MapleLoan_AcceptBorrower_NotPendingBorrowerError() instead of throwing "ML:AB:NOT_PENDING_BORROWER".
