---
id: 25129
severity: "Low/Info"
---

# Erc20Utils::safeTransferFrom() assumes the tokens are transferred to this, which may not be the case

## Description

Erc20Utils::safeTransferFrom() checks the balance of address(this) before and after transferring, but it may transfer the tokens to a different address, in which case it would always return 0. The function is not used in the codebase but may be in the future.

## Proof of Concept

No PoC provided.

## Recommendation

The balances should be checked of the to address, not address(this).
