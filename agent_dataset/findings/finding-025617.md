---
id: 25617
severity: "Low/Info"
---

# StakingOperator::setCollateralToken() will cause issues if it changes tokens relations that have already been set

## Description

Tokens are locked and unlocked, minting and burning zkTokens in the process, respectively. Thus, if zkTokens have been minted, but then the mappings between original and collateral tokens are changed, it will burn other zkTokens, leading to issues.

## Proof of Concept

No PoC provided.

## Recommendation

Either place an explicit check in the function to ensure the mappings have not been already created or keep this in mind.
