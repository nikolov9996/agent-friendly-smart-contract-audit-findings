---
id: 25404
severity: "Low/Info"
---

# BasicVaultFactory::createVault() inconsistent already existing vault check

## Description

BasicVaultFactory::createVault() reverts with a vault already created error whenever $.vaultIds[vault] != 0 && $.vaults[$.vaultIds[vault]] != vault.

This is problematic because the vault with id == 0 will not revert due to this error (but still reverts later as the creation will fail) and $.vaults[$.vaultIds[vault]] is always vault, as it is impossible to have mismatching vaults and vault ids.

## Proof of Concept

No PoC provided.

## Recommendation

Vault ids could start at 1 instead so index 0 is never confused with not having been created. This way it is enough checking the vault to id mapping.
