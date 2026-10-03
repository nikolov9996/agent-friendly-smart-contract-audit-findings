---
id: 25215
severity: "Low/Info"
---

# PreDepositVault::maxDeposit/Mint() are missing maxDepositLimit as per the ERC4626 spec

## Description



## Proof of Concept

## Vulnerability Detail

From the [spec](<https://eips.ethereum.org/EIPS/eip-4626#maxdeposit>),

> MUST factor in both global and user-specific limits

## Impact

Non EIP4626 compliance

## Code Snippet

[https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdUSDT.sol#L18](<https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdUSDT.sol#L18>)

## Recommendation

Override `ERC4626::maxDeposit/mint()` and implement the deposit limit there
