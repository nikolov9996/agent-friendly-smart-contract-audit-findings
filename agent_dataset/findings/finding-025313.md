---
id: 25313
severity: "Medium"
---

# Pool Delegates can accidentally lock out of their funds LPs in the middle of redeeming.

## Description

Pool delegates are allowed to change the withdrawal manager address at any time using the setWithdrawalManager() function. Changing this address, even with good intentions in mind, poses the problem of locking out of their shares the LPs in the process of redeeming.

This happens since the storage mappings: exitCycleId and lockedShares, as well as the ERC-20 tokens (shares) of the LPs waiting for their withdrawal window will not have migrated to the new address, and will now be locked in the previous withdrawalManager proxy contract.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the setWithdrawalManager() function or pause it by default.
