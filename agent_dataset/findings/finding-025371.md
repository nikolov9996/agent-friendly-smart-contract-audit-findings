---
id: 25371
severity: "Low/Info"
---

# owner in SyrupRouter also requires transfer permission

## Description

SyrupRouter::_deposit() checks for owner permission to deposit, but due to [transferring](<https://github.com/maple-labs/syrup-router/blob/main/contracts/SyrupRouter.sol#L67>) the shares later in ERC20Helper::transfer(), it also requires P:transfer permission.

## Proof of Concept

No PoC provided.

## Recommendation

According to the specifications, P:transfer and P:transferFrom should be permissionless, so this is not a problem. However, consider adding a comment in the code.
