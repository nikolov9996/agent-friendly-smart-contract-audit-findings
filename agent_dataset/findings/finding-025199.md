---
id: 25199
severity: "Low/Info"
---

# Don't return the same memory variable if your passing it as argument

## Description

In BaseRouter, _bundleInternal(...), the tokensToCheck array is updated in tokensToCheck = _addTokenToList(token, tokensToCheck);. In _addTokenToList(...), the token is added to the array if it is not present yet, which modifies the tokensToCheck in the outer scope of the function; there is no need to return it

- when a variable is passed as memory to an internal function, the same memory location is used, solidity does not create a copy.

## Proof of Concept

No PoC provided.

## Recommendation

Change _addTokenToList(...) to not return anything.
