---
id: 25260
severity: "Low/Info"
---

# KeyringCoreV2Base::blacklistEntity() and KeyringCoreV2Base::unblacklistEntity() could check that the addresses are not already set

## Description

KeyringCoreV2Base::blacklistEntity() and KeyringCoreV2Base::unblacklistEntity() could perform additional checks such that the address is not already blacklisted or not. It has no impact but could be important to warn the admin about potential mistakes, as not reverting would likely go unnoticed.

Additionally, other permissioned functions such as KeyringCoreV2Base::registerKey() or KeyringCoreV2Base::revokeKey() perform similar checks.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if the address is already blacklisted or not blacklisted.
