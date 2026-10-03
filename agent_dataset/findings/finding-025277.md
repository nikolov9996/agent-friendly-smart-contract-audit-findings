---
id: 25277
severity: "Low/Info"
---

# Unnecessary currentEpoch zero check in StandardGovernor and ThresholdGovernor

## Description

The currentEpoch value is derived from [BatchGovernor._clock](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/abstract/BatchGovernor.sol#L419-L421>), which can never be zero. But the execute functions of both StandardGovernor and ThresholdGovernor check if currentEpoch is zero.

## Proof of Concept

No PoC provided.

## Recommendation

Since the epoch implementation being used doesn't allow for a zero value returned by _clock, consider removing these zero checks.
