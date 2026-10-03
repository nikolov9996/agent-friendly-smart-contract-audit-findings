---
id: 25358
severity: "Low/Info"
---

# MapleSkyStrategy::assetsUnderManagement() uses maxWithdraw(), which may return 0

## Description

MapleSkyStrategy::assetsUnderManagement() uses maxWithdraw(), which according to EIP4626 returns 0 when the withdrawal limit is reached or similar. The SavingsUsds contract is upgradeable, so even if it currently returns the correct value, it may be upgraded in the future, adding a withdrawal limit.

This would bring concerns in regards to silently reporting 0 assets.

## Proof of Concept

No PoC provided.

## Recommendation

Although not a problem right now, consider calling balanceOf() followed by previewRedeem().
