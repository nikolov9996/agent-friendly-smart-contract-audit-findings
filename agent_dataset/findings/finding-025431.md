---
id: 25431
severity: "Medium"
---

# Vault cap is not considered in the maxDeposit() calculations, which may make deposits fail

## Description

LoopStrategy::maxDeposit() does not consider the vault cap, which limits the amount that can be deposited if the utilization rate is close to the targetUtilization.

Hence, deposits will revert.

## Proof of Concept

No PoC provided.

## Recommendation

Consider incorporating the maxDeposit() of the vault.
