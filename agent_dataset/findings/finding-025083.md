---
id: 25083
severity: "Crit/High"
---

# Scheduled withdrawals with unsupported tokens will be halted

## Description

A token might be supported at time A, letting users withdraw in BatchOut using this token. However, if the token is not supported anymore after withdrawals are scheduled, it won't be possible to call BatchOut:executeBatchWithdrawFromStrategyWithSwap(), as it will revert when trying to call router.withdrawFromStrategies(), [here](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/StrategyRouter.sol#L400-L402>).

The workaround is supporting the token for a short period of time again to let users fulfill their withdrawals, but this could lead to other problems, given that it was previously deprecated.

## Proof of Concept

No PoC provided.

## Recommendation

Change the withdraw token to another supported token in executeBatchWithdrawFromStrategyWithSwap() if the token is no longer supported.
