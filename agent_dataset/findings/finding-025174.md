---
id: 25174
severity: "Crit/High"
---

# safeApprove(...) reverts if approval is different than 0, use safeIncreaseAllowance(...) instead

## Description

The BaseRouter interacts with the vault and some actions require tokens being pulled from the BaseRouter to the vault, which means that the BaseRouter must first approve the vault. This approval is using SafeERC20 safeApprove(...), which is deprecated and should not be used due to the fact that it reverts if the allowance of pair owner and spender is not 0.

This allowance should always be 0 for most tokens and situations when safeApprove(...) is called, given that the tokens are spent right after the approval is emitted.

However, some weird tokens or behaviour could lead to not all tokens being spent, which would freeze the BaseRouter actions that require approval.

## Proof of Concept

No PoC provided.

## Recommendation

Use safeIncreaseAllowance(...) instead of safeApprove(...).
