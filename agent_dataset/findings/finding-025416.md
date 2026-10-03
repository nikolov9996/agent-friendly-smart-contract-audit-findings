---
id: 25416
severity: "Low/Info"
---

# Cap::receive() does not place restrictions in the sender, which may lead to donations

## Description

Cap::receive() has no restrictions in place of the msg.sender, which means anyone can send funds to Cap, without any effect.

## Proof of Concept

No PoC provided.

## Recommendation

Delete the function or specify who may call it.
