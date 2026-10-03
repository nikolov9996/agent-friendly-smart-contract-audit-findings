---
id: 25235
severity: "Crit/High"
---

# In glAVAX, function _rebalanceWithdraw() withdraws incorrect amount from WAVAX address

## Description

In the function _rebalanceWithdraw() if it is necessary to withdraw from WAVAX in order to satisfy a withdrawal, the [code](<https://github.com/threesigmaxyz/glacier-contracts-foundry/blob/audit-12-07-2023/contracts/protocol/GlacialAVAX/glAVAX.sol#L666>) will compare the balance of the WAVAX contract and how much is needed to satisfy the withdrawal.

When doing this comparison, if it finds that the balance of the WAVAX contract is bigger than how much is needed to satisfy the withdrawal, then it should only withdraw how much it needs.

If the opposite happens it should only withdraw the balance in the WAVAX contract. Currently the code does the opposite.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
