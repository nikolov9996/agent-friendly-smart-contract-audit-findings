---
id: 25425
severity: "Low/Info"
---

# The StrategyExecutor can remain in a paused state if the owner renounces control while it's paused

## Description

The StrategyExecutor contract inherits Ownable2StepUpgradeable and PausableUpgradeable, allowing the owner to pause the contract. The issue arises if the contract is paused and the owner renounces ownership, leaving the contract permanently paused.

## Proof of Concept

No PoC provided.

## Recommendation

Consider removing the option for renouncing ownership or reimplementing the logic to ensure the contract unpauses before ownership is renounced.
