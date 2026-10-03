---
id: 25716
severity: "Medium"
---

# Stuck tokens due to not using SafeTransfer

## Description

[reclaimToken()](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/wTIA.sol#L75>) does not use [SafeERC20.safeTransfer()](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/utils/SafeERC20.sol#L36>), which could lead to stuck tokens.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
