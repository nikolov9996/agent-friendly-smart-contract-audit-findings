---
id: 25060
severity: "Crit/High"
---

# Rank and multiplier of a user can not be set if the user is registered for MetaIDO by the admin

## Description

`IDOPoolAbstract::adminAddRegForMetaIDO()` sets `metaIDO.isRegistered[user] = true;`, but not the rank and multiplier. In `IDOPoolAbstract::registerForMetaIDO()` it reverts if the user is already registered `require(!metaIDO.isRegistered[msg.sender], "User already registered");`. Thus, it will be impossible to set the rank or multiplier for users registered by the admin.

Additionally, there is unreachable code, `if (metaIDO.isRegistered[msg.sender])` is always `false` due to the check above requiring the user to not have been registered previously.

## Proof of Concept

No PoC provided.

## Recommendation

There are a few solutions, for example, when manually registering a user by the admin, the rank and multiplier can be fetched from the multiplier contract.
