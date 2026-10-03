---
id: 25219
severity: "Medium"
---

# PreDepositVault will not work for USDT

## Description



## Proof of Concept

## Vulnerability Detail

USDT does not return on approval, which makes the EVM revert as it has return length checks and it expects it to return true.

## Impact

Deployment of `PreDepositVault` for USDT fails.

## Code Snippet

[https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdUSDT.sol#L47](<https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdUSDT.sol#L47>)

## Recommendation

Use `.forceApprove()` from `SafeERC20`.
