---
id: 25312
severity: "Low/Info"
---

# Unbounded loops in MapleWithdrawalManager may break in the future if the withdrawal windows are small

## Description

Loops revert due to OOG errors if too many iterations are performed. Some functions will stop working if these loops grow too large. For example, [`getConfigAtId(uint256 cycleId_)`](<https://github.com/maple-labs/withdrawal-manager-cyclical-private/blob/95212a0adb2853420e60d094c01323274979cb75/contracts/MapleWithdrawalManager.sol#L317>) may be called with a cycleId_ well in the past, leading to OOG.

The likelihood of this happening depends on the number of times the configs were changed and the cycle durations. Due to this, it might make it impossible to call removeShares(), so the shares would be stuck.

## Proof of Concept

No PoC provided.

## Recommendation

Send hints in these functions (or make them internal and create 2 external functions, one with hints and another the same as the current one).

For example, getConfigAtId(uint256 cycleId_) could receive latestConfigIdHint_ as argument.
