---
id: 25351
severity: "Low/Info"
---

# Aave RewardsController can add Usdc to the rewards list and the strategy has no way to collect the rewards

## Description

The Aave strategy does not deal with the reward controller, so it could miss out on rewards emitted in case the fundsAsset is listed in the RewardsController.

## Proof of Concept

No PoC provided.

## Recommendation

Although the RewardsController does not currently emit rewards for Usdc, which is the asset that is going to be supported, consider adding the functionality to collect rewards.
