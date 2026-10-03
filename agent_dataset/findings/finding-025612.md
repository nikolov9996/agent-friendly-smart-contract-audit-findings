---
id: 25612
severity: "Low/Info"
---

# Missing proof identifier, which could lead to using the same proof in another method

## Description

There is no identifier in the circuits corresponding to the method that the proof relates to. This means that if 2 circuits have exactly the same inputs, the same proof could be used for more than 1 method.

Thus, if a user intended to do some action, when the proof became exposed in the mempool, it could be used to perform another action. There are no known situations where the same proof can be used, but it is still a possibility.

## Proof of Concept

No PoC provided.

## Recommendation

Each circuit should have an identifier such that the proof can only match to prevent using it in another method.
