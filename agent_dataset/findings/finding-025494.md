---
id: 25494
severity: "Medium"
---

# Balance check in Vault::withdraw() does not take fees into account

## Description

Vault::withdraw() transfers funds to an user if address([this](<https://github.com/nomad-xyz/ExcessivelySafeCall/blob/main/src/ExcessivelySafeCall.sol#L24>))).balance >= amount, which may transfer funds resulting from fees.

## Proof of Concept

No PoC provided.

## Recommendation

Replace the check by address(this)).balance - totalFees >= amount to make sure fees can always be withdrawn.
