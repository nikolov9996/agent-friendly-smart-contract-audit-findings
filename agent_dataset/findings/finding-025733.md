---
id: 25733
severity: "Low/Info"
---

# Missing pagination for some functions that iterate

## Description

[ArbAirdrop::getClaimed()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/ArbAirdrop.sol#L91-L93>) may revert after enough weeks have passed due to OOG.

[BaseEngine::getHealthContribution()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/BaseEngine.sol#L120>) may revert if enough productIds are set.

## Proof of Concept

No PoC provided.

## Recommendation

Add initial and final weeks arguments.
