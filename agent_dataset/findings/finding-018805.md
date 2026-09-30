---
id: 18805
severity: "High"
---

# `_voteSucceeded`

## Description

As a result, voting process is broken, as it won’t execute proposals with most of `forVotes`. Instead, it will execute proposals with most of `againstVotes`.

## Proof of Concept

It returns whether number of votes with support = 1 is greater than with support = 0:
    
```solidity
function _voteSucceeded(uint256 proposalId) internal view override returns (bool){
    return proposalData[proposalId].supportVotes[1] > proposalData[proposalId].supportVotes[0];
}
```

However support = 1 means `againstVotes`, and support = 0 means `forVotes`:

```solidity
function proposals(uint256 proposalId) external view returns (...) {
    ...
    forVotes =  proposalData[proposalId].supportVotes[0];
    againstVotes =  proposalData[proposalId].supportVotes[1];
    abstainVotes =  proposalData[proposalId].supportVotes[2];
    ...
}
```

## Recommendation

Swap 1 and 0:
    
```solidity
function _voteSucceeded(uint256 proposalId) internal view override returns (bool){
    return proposalData[proposalId].supportVotes[0] > proposalData[proposalId].supportVotes[1];
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the governance contract’s internal vote‑success check. The function that determines whether a proposal has passed compares the number of votes stored at index 1 with the number stored at index 0 and returns true when the former is greater. In this contract the vote mapping is defined such that index 0 represents the count of "for" votes and index 1 represents the count of "against" votes. Consequently the success condition is inverted: a proposal is considered successful when it has more against votes than for votes. This logical inversion breaks the intended voting process because proposals that the community overwhelmingly rejects are executed, while proposals that receive majority support are discarded. The bug is triggered each time a proposal’s voting period ends and the contract evaluates _voteSucceeded to decide whether to enact the proposal. All participants in the governance system—token holders, proposal creators, and the protocol itself—are affected because the outcome of governance decisions no longer reflects the expressed preferences of the voters. The issue was uncovered during a formal audit when the auditor compared the public view function that reports forVotes and againstVotes with the internal success check and noticed the mismatch. It can be hard to spot in normal operation because the UI correctly displays the vote tallies, yet the execution result contradicts those numbers, leading users to see proposals they voted for being rejected and proposals they voted against being approved. Exploitation is straightforward: an attacker can craft or promote a malicious proposal and simply gather enough opposition votes, which the contract mistakenly treats as support, causing the proposal to pass without needing any genuine backing. The impact includes unauthorized protocol upgrades, fund transfers, or parameter changes that were never intended by the community, effectively compromising the protocol’s security and trust model. To remediate, the comparison should be swapped so that the function returns true when the count of for‑votes exceeds the count of against‑votes, aligning the logical condition with the semantic meaning of the stored vote indices. This correction restores the intended governance semantics, ensuring that proposals only pass when they have genuine majority support.
