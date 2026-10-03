---
id: 25502
severity: "Low/Info"
---

# Fee event is missing in the constructors of BRC20Factory and Vault

## Description

The fee is set in the constructors of BRC20Factory and Vault, but the event is not emitted.

## Proof of Concept

No PoC provided.

## Recommendation

Emit the FeeChanged event in the constructor of both contracts.
