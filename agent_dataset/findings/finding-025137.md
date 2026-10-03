---
id: 25137
severity: "Low/Info"
---

# TokenVault allows withdrawals using offchain logic, so the offchain service must take into consideration reorgs

## Description

TokenVault does not track or set the withdrawal logic on chain, so care must be taken in the offchain components due to reorgs. If users deposit and are awarded a withdrawal in a short time frame, a reorg could happen which ends up removing the deposit, but the user still has the withdrawal signature.

## Proof of Concept

No PoC provided.

## Recommendation

The fix is in the offchain component, which is making sure there is a delay between a deposit and the ability of a user to withdraw. The protocol is going to be deployed on Blast, which is unlikely to have reorgs, but it is still a good practice.
