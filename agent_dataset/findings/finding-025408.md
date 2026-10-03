---
id: 25408
severity: "Low/Info"
---

# Protocol should disable renouncing ownership if it is never intended

## Description

Contracts inheriting Ownable2StepUpgradeable or Ownable allow for renouncing ownership, which could be catastrophic if triggered by mistake.

## Proof of Concept

No PoC provided.

## Recommendation

Consider overriding renounceOwnership() to revert if called, disabling this functionality.
