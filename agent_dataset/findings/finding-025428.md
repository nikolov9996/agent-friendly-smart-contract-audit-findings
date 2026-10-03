---
id: 25428
severity: "Low/Info"
---

# Storage variables can be cached to save gas

## Description

Storage variables should be cached to avoid reading from storage more than once and incurring extra gas costs.

## Proof of Concept

No PoC provided.

## Recommendation

In BasicVault::enableEOL(), $.asset.forceApprove(address($v2.eol), type(uint256).max); should use eol instead. In RedeemQueue::push(), queue._count++; could be queue._count = requestId + 1. In RedeemQueue::resolve(), update() writes the whole request to storage, when only the resolved at field is modified.

In StrategyExecutor::disableStrategy, enabled.length should be cached.
