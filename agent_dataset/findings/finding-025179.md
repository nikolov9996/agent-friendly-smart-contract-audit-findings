---
id: 25179
severity: "Low/Info"
---

# _getBeneficiaryFromCalldata(...) in ConnextRouter should not allow the first action to be depositETH(...)

## Description

Currently issue 3S-FUJI-M07 means that the deposit action can't be performed on a cross transfer at all. Still, having fixed it, the first action should not be depositETH(...), as there is no ETH to be deposited yet (unless users are using the balance of the ConnextRouter in the other chain, which should not be intended).

## Proof of Concept

No PoC provided.

## Recommendation

In _getBeneficiaryFromCalldata(...), revert if the first action is depositETH(...). Flashloans would not be able to call depositETH(...) in the first action, which is okay because they send ERC20s anyway.
