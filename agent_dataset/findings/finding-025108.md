---
id: 25108
severity: "Low/Info"
---

# All functions could have a started modifier as they should not be called before the start time

## Description

Only `Codeup::addGameETH()` checks if the protocol has started in `require(block.timestamp > startUNIX, NotStarted());`, but the same checks could be applied to the remaining functions. Although this presents no vulnerability as these functions will not do anything before adding `gameETH`, it is a good practice to prevent unwanted behaviours.

## Proof of Concept

No PoC provided.

## Recommendation

Create a modifier having `require(block.timestamp > startUNIX, NotStarted());` and place it in all functions.
