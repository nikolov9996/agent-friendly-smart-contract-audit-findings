---
id: 25214
severity: "Low/Info"
---

# YieldVault maxRedeem(...) unnecessarily converts shares to assets and back to shares again

## Description

maxRedeem(...) enables users to know how many shares they can redeem. In the case of the borrowing vault, it depends on the amount of debt a user has taken, which is taken into account in _computeFreeAssets(...). In the case of the yield vault, maxRedeem(...) is the balance of the user.

Currently, it converts the balance of the user to assets in _computeFreeAssets(...), and then in maxRedeem(...) back to shares again. This is unnecessary and the code could be refactored to handle these 2 situations.

## Proof of Concept

No PoC provided.

## Recommendation

The YieldVault could override maxRedeem(...) and return the balance of the user directly (if not paused).
