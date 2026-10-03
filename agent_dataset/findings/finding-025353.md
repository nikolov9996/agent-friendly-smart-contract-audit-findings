---
id: 25353
severity: "Low/Info"
---

# ERC4626::previewRedeem() may revert, which will DoS MaplePool withdrawals

## Description

The EIP4626 interface says for previewRedeem() that it may revert, which will DoS withdrawals in the MaplePool:

> MAY revert due to other conditions that would also cause redeem to revert.

## Proof of Concept

No PoC provided.

## Recommendation

This should be analyzed on a case by case basis for each underlying ERC4626 vault.
