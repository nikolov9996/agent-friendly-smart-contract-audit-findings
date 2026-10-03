---
id: 25301
severity: "Low/Info"
---

# Unnecessary check in StandardGovernor.state

## Description

Since [StandardGovernor._votingPeriod](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/StandardGovernor.sol#L439>) function will always returns 0, voteStart will always be equal to voteEnd.

This means that the following check in the StandardGovernor.state is unnecessary: if (currentEpoch_ <= voteEnd_) return ProposalState.Active; The use of < spends unnecessary gas by checking that currentEpoch_ is less than voteEnd_.

If currentEpoch_ is indeed less that voteEnd_ then the transaction will stop a few lines above: if (currentEpoch_ < voteStart_) return ProposalState.Pending;

## Proof of Concept

No PoC provided.

## Recommendation

The check for strict equality (==) will suffice.
