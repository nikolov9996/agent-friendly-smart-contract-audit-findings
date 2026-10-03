---
id: 25216
severity: "Low/Info"
---

# PreDepositVault::sweep() uses address.transfer which does not work for certain wallets

## Description



## Proof of Concept

## Vulnerability Detail

Admin calls `PreDepositVault::sweep()` using a smart contract wallet but it reverts trying to transfer native out.

## Impact

Admin can't sweep ETH.

## Code Snippet

[https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L89](<https://github.com/sherlock-audit/2025-03-gaib/blob/main/pre-vaults/contracts/pre-vaults/gpdWBTC.sol#L89>)

## Recommendation

Use `sendValue()` [https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/Address.sol#L33.](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/Address.sol#L33>)
