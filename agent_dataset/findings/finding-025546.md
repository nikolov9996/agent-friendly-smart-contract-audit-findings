---
id: 25546
severity: "Low/Info"
---

# OstiumRegistry should disable renouncing ownership if it is never intended

## Description

[OstiumRegistry](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-fe>) allows renouncing ownership by inheriting Ownable, which could be catastrophic if triggered by mistake.

## Proof of Concept

No PoC provided.

## Recommendation

Consider overriding renounceOwnership() and revert if called to disable this functionality.
