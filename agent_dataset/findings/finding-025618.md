---
id: 25618
severity: "Crit/High"
---

# In StakingAssetManager::lockERC20() the resulting note is created with asset instead of zkToken

## Description

Users can transfer tokens to the StakingAssetManager in return for a note commitment of the corresponding zkToken. However, StakingAssetManager::lockERC20() builds the note using args.asset, which is the asset itself, which will lead to problems (will not be able to unlock).

## Proof of Concept

No PoC provided.

## Recommendation

Build the note using zkToken instead.
