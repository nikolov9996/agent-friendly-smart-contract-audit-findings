---
id: 25315
severity: "Low/Info"
---

# Borrowers can prevent MapleLoanInitializer from initializing a loan by using a vanity address.

## Description

By using the fallback function in the MapleLoanInitializer to initialize a loan (both for open term and for fixed term) it allows the borrower to choose a vanity address to end up in any public function of the MapleLoanInitializer, preventing the _initialize() to set the starting parameters.

This happens because the address of the borrower (which is not controlled by the protocol) is the first argument of the decode argument function which will mean that its first bytes will try to be matched to a function selector before ending up in the fallback

```solidity
function. The contract has several public functions (getters for the public variables in storage & others), so there are several combinations that could lead to this situation. This
```

logic is also used throughout the repo in other initializer contracts. At the moment, no one can take advantage of an uninitialized loan, due to all of the checks existing in the code, however, this is still a vulnerability of the deployment logic used throughout the repo to initialize contracts, and could lead to more significant exploits in future updates.

## Proof of Concept

No PoC provided.

## Recommendation

Have the first argument of the initializer be a protocol-controlled address, like the lender.
