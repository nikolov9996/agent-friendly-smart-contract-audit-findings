---
id: 25300
severity: "Low/Info"
---

# Unnecessary conditional check in ThresholdGovernance.execute

## Description

The function [ThresholdGovernor.execute](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/abstract/ThresholdGovernor.sol#L41-L56>) executes a successful proposal. Among other things, the function executes the following lines:

```solidity
if (currentEpoch_ == 0) revert InvalidEpoch();
// Proposals have voteStart=N and voteEnd=N+1, and can be executed
only during epochs N and N+1.
uint16 latestPossibleVoteStart_ = currentEpoch_;
uint16 earliestPossibleVoteStart_ = latestPossibleVoteStart_ > 0 ? latestPossibleVoteStart_ - 1 : 0;
```

The execute function will revert if currentEpoch_ == 0, and then it assigns this value to latestPossibleVoteStart_. Considering this last variable can never be zero, the conditional check in the following line is unnecessary.

## Proof of Concept

No PoC provided.

## Recommendation

Replace the last lined shown above with the following: uint16 earliestPossibleVoteStart_ = latestPossibleVoteStart_ - 1;
