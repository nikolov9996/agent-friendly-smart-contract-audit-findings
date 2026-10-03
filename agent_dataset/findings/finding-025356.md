---
id: 25356
severity: "Low/Info"
---

# tin in the Psm will cause an instant drop in the share price which could be leveraged by Maple Pool users

## Description

Currently tin is null in the Psm, but if it was non null, it would instantly lead to a reduction in the totalAssets() in the Maple Pool, as a fee would be taken when converting fundsAssets to Usds in the Sky Strategy, when requesting funds.

This would allow Maple Pool users to frontrun the MapleSkyStrategy::fundStrategy() and withdraw, avoiding the fee, making unaware users pay for this. Then, they could redeposit to keep earning fees. The damage is limited by the withdrawal mechanism.

## Proof of Concept

No PoC provided.

## Recommendation

Consider procedures to safely request funds without allowing users to escape the fee.
