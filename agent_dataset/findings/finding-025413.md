---
id: 25413
severity: "Low/Info"
---

# BasicVault::manualRedeem() and BasicVault::manualDeposit() are inconsistent

## Description

BasicVault::manualDeposit() does not pull assets from the msg.sender, but BasicVault::manualRedeem() burns shares from msg.sender, which is inconsistent. In fact, BasicVault::manualRedeem() is exactly the same as BasicVault::redeem(), the only difference being that the former is permissioned.

## Proof of Concept

No PoC provided.

## Recommendation

The purpose of BasicVault::manualRedeem() is unclear.
