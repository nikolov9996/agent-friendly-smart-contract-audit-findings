---
id: 25394
severity: "Low/Info"
---

# completeUnstake() not following checks-effects-interactions pattern

## Description

completeUnstake() transfers tokens before deleting the information of the staker, not following the checks-effects-interactions pattern.

## Proof of Concept

No PoC provided.

## Recommendation

Delete the staker mapping before transferring the tokens.
