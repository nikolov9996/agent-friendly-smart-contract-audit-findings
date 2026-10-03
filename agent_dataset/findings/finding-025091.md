---
id: 25091
severity: "Low/Info"
---

# PHyperLPoolSwapInside::_swapWithCustomData() .approve() reverts for tokens that don't return a boolean

## Description

[PHyperLPoolSwapInside::_swapWithCustomData()](<https://github.com/ClipFinance/StrategyRouter-private/pull/107/files#diff-023946f07f510e865612a28a9a222e00f0f6b90a253fd981e9bf4f7656f5497fR581>) [uses](<https://github.com/ClipFinance/StrategyRouter-private/pull/107/files#diff-023946f07f510e865612a28a9a222e00f0f6b90a253fd981e9bf4f7656f5497fR596>) unsafe .approve() which does not return a bool on some tokens, reverting.

## Proof of Concept

No PoC provided.

## Recommendation

Use .forceApprove().
