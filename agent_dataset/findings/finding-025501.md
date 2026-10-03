---
id: 25501
severity: "Medium"
---

# Equality check should be performed for fees, not >= as it can lead to users sending more fees than supposed

## Description

In BRC20Factory::burn(), Vault::deposit(), it is required that the fee is equal to or exceeds the msg.value. However, this could lead to loss of fees, as the fee can be lowered without users noticing (or frontrunning them), and users would lose this part of the fee.

In the case of the Vault, these funds would be left untracked because the fees are tracked in totalFees, so the owner would not be able to withdraw these extra funds.

## Proof of Concept

No PoC provided.

## Recommendation

Replace the >= checks for ==. The equality check should be performed for fees, not >= as it can lead to users sending more fees than supposed
