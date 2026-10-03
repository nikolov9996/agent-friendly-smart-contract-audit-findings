---
id: 25401
severity: "Low/Info"
---

# In AggregateHook, several if (newAmount == 0) checks are ambiguous

## Description

In AggregateHook::reportRedeem(), AggregateHook::previewReportClaim() and AggregateHook::reportClaim(), it sets newAmount to prevAmount if newAmount is null, which is always, as it is initialized by default to null.

## Proof of Concept

No PoC provided.

## Recommendation

Modify the code to make the intent more clear.
