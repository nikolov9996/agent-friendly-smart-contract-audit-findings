---
id: 25193
severity: "Low/Info"
---

# _handleSwapAction(...) creates situations where the arguments receiver and sweeper need to be the same address in BaseRouter

## Description

In _handleSwapAction(...) the function checks if both the receiver and sweeper are the beneficiary given certain conditions. Since there can only be one beneficiary there are situations where a user can't name the receiver and sweeper as two different addresses.

## Proof of Concept

No PoC provided.

## Recommendation

This should be explained as expected behavior in the documentation or in comments.
