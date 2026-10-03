---
id: 25309
severity: "Low/Info"
---

# Operational Admin Suggestions

## Description

- MapleWithdrawalManager:setExitConfig() could be performed by the operational admin, since it can call [`setPendingDelegate()`](<https://github.com/maple-labs/pool-v2-private/blob/c8d9cbf8edecccb53323aa91d71b719ac4230c3e/contracts/MaplePoolManager.sol#L150>) and acquire the permissions anyway.
- Delegates could choose whether they wanted the operational admin to have their permissions, basically delegating their role.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
