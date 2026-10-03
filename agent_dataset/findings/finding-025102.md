---
id: 25102
severity: "Low/Info"
---

# Codeup::claimCodeupERC20() is vulnerable to sandwich attacks

## Description

`Codeup::claimCodeupERC20()` does not set minimum values for adding liquidity or swapping (sets 0) and places a deadline of `block.timestamp`, which means mev bots may sandwich these calls for profit for the protocol's loss.

## Proof of Concept

No PoC provided.

## Recommendation

Send the minimum amounts as argument as well as the deadline.
