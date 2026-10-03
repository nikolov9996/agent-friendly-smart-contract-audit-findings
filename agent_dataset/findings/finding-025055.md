---
id: 25055
severity: "Crit/High"
---

# Cancelling rounds after finalizing will lead to incorrect globalTokenAllocPerIDORound tracking

## Description

Rounds may be claimed after finalized, in which each claim reduces `globalTokenAllocPerIDORound[idoConfig.idoToken]`. When rounds are canceled and were enabled, `globalTokenAllocPerIDORound[idoConfig.idoToken]` is reduced by `idoConfig.idoSize`.

Thus, it's possible for the `globalTokenAllocPerIDORound` to be reduced by more than `idoConfig.idoSize` per round in case it is finalized and canceled. This means that other rounds could not be claimed as `globalTokenAllocPerIDORound` would underflow as it had been reduced too much and it may not be possible to cancel them as it may underflow.

## Proof of Concept

No PoC provided.

## Recommendation

According to specs, rounds should be allowed to be canceled after finalized, so `globalTokenAllocPerIDORound[idoConfig.idoToken]` must be reduced by the amount left of `idoTokens` that were not claimed. A new variable needs to be created to track the amount of tokens that were claimed per round, such that on cancel after finalizing, `globalTokenAllocPerIDORound` can be decreased by `globalTokenAllocPerIDORound.idoTokensSold - idoRoundConfigs[idoRoundId].idoTokensClaimed`.

Additionally, users should not be able to participate or claim if a round was canceled.
