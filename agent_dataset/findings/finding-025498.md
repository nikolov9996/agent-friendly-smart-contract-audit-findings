---
id: 25498
severity: "Low/Info"
---

# BRC20Factory::burn() could validate the receiver length

## Description

BRC20Factory::burn() does not validate the receiver, which could lead to wasted funds. It's impossible to do a fail safe verification, but at least the length could be checked.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if the length of the receiver is null.
