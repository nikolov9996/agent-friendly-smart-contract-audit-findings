---
id: 25272
severity: "Low/Info"
---

# castVoteWithReason always fires a VoteCast event with an empty reason

## Description

The [BatchGovernor](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/abstract/BatchGovernor.sol>) contract supports castVoteWithReason to be compatible with certain governors.

Because the VoteCast event has a reason parameter, whoever uses this external function is expecting an event being emitted with the provided reason.

Instead, the reason parameter is always empty in the event being emitted by _castVote:

```solidity
function _castVote(address voter_, uint256 weight_, uint256 proposalId_, uint8 support_) internal virtual {
    // ... emit VoteCast(voter_, proposalId_, support_, weight_, "");
}
```

## Proof of Concept

No PoC provided.

## Recommendation

Make sure that the reason input of castVoteWithReason is passed through to the VoteCast event.
