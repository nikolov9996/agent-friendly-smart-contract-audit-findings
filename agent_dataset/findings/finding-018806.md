---
id: 18806
severity: "High"
---

# Governance wrongly calculates `_quorumReached`

## Description

For some reason it is calculated as sum of `againstVotes` and `abstainVotes` instead of `totalVotes` on proposal. As the result, quorum will be reached only if >=1/3 of all votes are abstain or against, which doesn’t make sense.

## Proof of Concept

Number of votes with support = 1 and support = 2 is summed up:
    
```solidity
function _quorumReached(uint256 proposalId) internal view override returns (bool){
    return proposalData[proposalId].supportVotes[1] + proposalData[proposalId].supportVotes[2] >= quorum(proposalSnapshot(proposalId));
}
```

However support = 1 means against votes, support = 2 means abstain votes:

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

Use `totalVotes`:
    
```solidity
function _quorumReached(uint256 proposalId) internal view override returns (bool){
    return proposalData[proposalId].totalVotes >= quorum(proposalSnapshot(proposalId));
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the governance contract’s quorum verification routine, which mistakenly adds only the counts of against votes and abstain votes when determining whether a proposal has reached the required quorum. In a correctly designed system, quorum should be measured against the total number of votes cast – the sum of for, against and abstain votes – because the purpose of quorum is to ensure that a sufficient portion of the voting population has participated, regardless of how they voted. The root cause is a logical error in the _quorumReached function: it references the supportVotes array indices that correspond to against (index 1) and abstain (index 2) instead of aggregating all three categories. As a result, the condition for quorum becomes "againstVotes + abstainVotes >= requiredQuorum". This means that quorum is considered reached only when at least one third of all votes are either against or abstain, which contradicts the intended governance model where any combination of votes that reaches the quorum threshold should be acceptable. An attacker can exploit this by casting a large number of abstain or against votes to artificially satisfy the quorum requirement while the number of supporting votes remains low, allowing a malicious proposal to be approved despite lacking genuine community backing. Conversely, honest proposals that receive many supporting votes may never meet quorum if the number of against or abstain votes is insufficient, causing legitimate governance actions to stall. The impact is high because it undermines the integrity of the decision‑making process, potentially leading to the execution of proposals that do not reflect the true will of token holders, and may affect the allocation of funds, protocol upgrades, or other critical actions. The bug manifests whenever a proposal’s vote tally is evaluated, i.e., during every call to _quorumReached, which occurs at the end of the voting period before a proposal can be queued or executed. All participants in the governance system – token holders, proposal creators, and the protocol itself – are affected because the outcome of votes cannot be trusted. The issue was discovered during a formal audit where the auditors compared the contract’s implementation against the documented governance specifications and identified the mismatch in vote aggregation. It can be hard to notice because the contract may still appear to function in simple test cases where the numbers of against and abstain votes happen to satisfy the quorum condition, masking the logical flaw. The proper fix is to replace the erroneous sum with a reference to the totalVotes field, ensuring that the quorum check compares the total number of votes cast against the required threshold. This aligns the implementation with standard governance patterns and restores confidence that proposals are approved only when a sufficient portion of the community has participated, regardless of vote direction. The bug belongs to the class of logical miscalculations in voting quorum logic, where an incorrect subset of vote categories is used to assess participation, leading to accounting errors and potential governance manipulation. From a user’s perspective the symptoms may include proposals that never pass despite many affirmative votes, or proposals that pass with almost no support, creating confusion when the UI reports "quorum reached" while the supporting vote count is near zero. The discrepancy violates the fundamental business rule that quorum should reflect overall participation, not a specific vote type, and can cause funds to be moved or protocol changes to be enacted without genuine consensus.
