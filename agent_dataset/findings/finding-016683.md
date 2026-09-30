---
id: 16683
severity: "Medium"
---

# User A cannot cancel User B’s proposal when User B’s prior number of votes at relevant block is same as proposal threshold, which contradicts the fact that User B actually cannot create the proposal when the prior number of votes is same as proposal threshold

## Description

When User B calls the following `propose` function for creating a proposal, it checks that User B’s prior number of votes at the relevant block is larger than the proposal threshold through executing `nouns.getPriorVotes(msg.sender, block.number - 1) > temp.proposalThreshold`. This means that User B cannot create the proposal when the prior number of votes and the proposal threshold are the same.

```solidity
function propose(
    address[] memory targets,
    uint256[] memory values,
    string[] memory signatures,
    bytes[] memory calldatas,
    string memory description
) public returns (uint256) {
    ProposalTemp memory temp;

    temp.totalSupply = nouns.totalSupply();

    temp.proposalThreshold = bps2Uint(proposalThresholdBPS, temp.totalSupply);

    require(
        nouns.getPriorVotes(msg.sender, block.number - 1) > temp.proposalThreshold,
        'NounsDAO::propose: proposer votes below proposal threshold'
    );
    require(
        targets.length == values.length &&
            targets.length == signatures.length &&
            targets.length == calldatas.length,
        'NounsDAO::propose: proposal function information arity mismatch'
    );
    require(targets.length != 0, 'NounsDAO::propose: must provide actions');
    require(targets.length <= proposalMaxOperations, 'NounsDAO::propose: too many actions');

    temp.latestProposalId = latestProposalIds[msg.sender];
    if (temp.latestProposalId != 0) {
        ProposalState proposersLatestProposalState = state(temp.latestProposalId);
        require(
            proposersLatestProposalState != ProposalState.Active,
            'NounsDAO::propose: one live proposal per proposer, found an already active proposal'
        );
        require(
            proposersLatestProposalState != ProposalState.Pending,
            'NounsDAO::propose: one live proposal per proposer, found an already pending proposal'
        );
    }

    temp.startBlock = block.number + votingDelay;
    temp.endBlock = temp.startBlock + votingPeriod;

    proposalCount++;
    Proposal storage newProposal = _proposals[proposalCount];
    newProposal.id = proposalCount;
    newProposal.proposer = msg.sender;
    newProposal.proposalThreshold = temp.proposalThreshold;
    newProposal.eta = 0;
    newProposal.targets = targets;
    newProposal.values = values;
    newProposal.signatures = signatures;
    newProposal.calldatas = calldatas;
    newProposal.startBlock = temp.startBlock;
    newProposal.endBlock = temp.endBlock;
    newProposal.forVotes = 0;
    newProposal.againstVotes = 0;
    newProposal.abstainVotes = 0;
    newProposal.canceled = false;
    newProposal.executed = false;
    newProposal.vetoed = false;
    newProposal.totalSupply = temp.totalSupply;
    newProposal.creationBlock = block.number;

    latestProposalIds[newProposal.proposer] = newProposal.id;

    /// @notice Maintains backwards compatibility with GovernorBravo events
    emit ProposalCreated(
        newProposal.id,
        msg.sender,
        targets,
        values,
        signatures,
        calldatas,
        newProposal.startBlock,
        newProposal.endBlock,
        description
    );

    /// @notice Updated event with `proposalThreshold` and `minQuorumVotes`
    /// @notice `minQuorumVotes` is always zero since V2 introduces dynamic quorum with checkpoints
    emit ProposalCreatedWithRequirements(
        newProposal.id,
        msg.sender,
        targets,
        values,
        signatures,
        calldatas,
        newProposal.startBlock,
        newProposal.endBlock,
        newProposal.proposalThreshold,
        minQuorumVotes(),
        description
    );

    return newProposal.id;
}
```

After User B’s proposal is created, User A can call the following `cancel` function to cancel it. When calling `cancel`, it checks that User B’s prior number of votes at the relevant block is less than the proposal threshold through executing `nouns.getPriorVotes(proposal.proposer, block.number - 1) < proposal.proposalThreshold`. When User B’s prior number of votes and the proposal threshold are the same, User A cannot cancel this proposal of User B. However, this contradicts the fact User B actually cannot create this proposal when the same condition holds true. In other words, if User B cannot create this proposal when the prior number of votes and the proposal threshold are the same, User A should be able to cancel User B’s proposal under the same condition but it is not true. The functionality for canceling User B’s proposal in this situation becomes unavailable for User A.

```solidity
function cancel(uint256 proposalId) external {
    require(state(proposalId) != ProposalState.Executed, 'NounsDAO::cancel: cannot cancel executed proposal');

    Proposal storage proposal = _proposals[proposalId];
    require(
        msg.sender == proposal.proposer ||
            nouns.getPriorVotes(proposal.proposer, block.number - 1) < proposal.proposalThreshold,
        'NounsDAO::cancel: proposer above threshold'
    );

    proposal.canceled = true;
    for (uint256 i = 0; i < proposal.targets.length; i++) {
        timelock.cancelTransaction(
            proposal.targets[i],
            proposal.values[i],
            proposal.signatures[i],
            proposal.calldatas[i],
            proposal.eta
        );
    }

    emit ProposalCanceled(proposalId);
}
```

## Proof of Concept

Please append the following test in the `NounsDAOV2#inflationHandling` `describe` block in `test\governance\NounsDAO\V2\inflationHandling.test.ts`. This test should pass to demonstrate the described scenario.

```solidity
it("User A cannot cancel User B's proposal when User B's prior number of votes at relevant block is same as proposal threshold, which contradicts the fact that User B actually cannot create the proposal when the prior number of votes is same as proposal threshold",
  async () => {
  // account1 has 3 tokens at the beginning
  // account1 gains 2 more to own 5 tokens in total
  await token.transferFrom(deployer.address, account1.address, 11);
  await token.transferFrom(deployer.address, account1.address, 12);

  await mineBlock();

  // account1 cannot create a proposal when owning 5 tokens in total
  await expect(
    gov.connect(account1).propose(targets, values, signatures, callDatas, 'do nothing'),
  ).to.be.revertedWith('NounsDAO::propose: proposer votes below proposal threshold');

  // account1 gains 1 more to own 6 tokens in total
  await token.transferFrom(deployer.address, account1.address, 13);

  await mineBlock();

  // account1 can create a proposal when owning 6 tokens in total
  await gov.connect(account1).propose(targets, values, signatures, callDatas, 'do nothing');
  const proposalId = await gov.latestProposalIds(account1.address);
  expect(await gov.state(proposalId)).to.equal(0);

  // other user cannot cancel account1's proposal at this moment
  await expect(
    gov.cancel(proposalId, {gasLimit: 1e6})
  ).to.be.revertedWith('NounsDAO::cancel: proposer above threshold');
  
  // account1 removes 1 token to own 5 tokens in total
  await token.connect(account1).transferFrom(account1.address, deployer.address, 13);

  await mineBlock();

  // other user still cannot cancel account1's proposal when account1 owns 5 tokens in total
  // this contradicts the fact that account1 cannot create a proposal when owning 5 tokens in total
  await expect(
    gov.cancel(proposalId, {gasLimit: 1e6})
  ).to.be.revertedWith('NounsDAO::cancel: proposer above threshold');

  // account1 removes another token to own 4 tokens in total
  await token.connect(account1).transferFrom(account1.address, deployer.address, 12);

  await mineBlock();

  // other user can now cancel account1's proposal when account1 owns 4 tokens in total
  await gov.cancel(proposalId, {gasLimit: 1e6})
  expect(await gov.state(proposalId)).to.equal(2);
});
```

## Recommendation

<https://github.com/code-423n4/2022-08-nounsdao/blob/main/contracts/governance/NounsDAOLogicV2.sol#L197-L200> can be changed to the following code.

```solidity
require(
    nouns.getPriorVotes(msg.sender, block.number - 1) >= temp.proposalThreshold,
    'NounsDAO::propose: proposer votes below proposal threshold'
);
```

or

<https://github.com/code-423n4/2022-08-nounsdao/blob/main/contracts/governance/NounsDAOLogicV2.sol#L350-L354> can be changed to the following code.

```solidity
require(
    msg.sender == proposal.proposer ||
        nouns.getPriorVotes(proposal.proposer, block.number - 1) <= proposal.proposalThreshold,
    'NounsDAO::cancel: proposer above threshold'
);
```

but not both.

We agree that the case of prior votes equal to `proposalThreshold` is missed, and plan to include that state in what is cancelable.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a boundary‑condition inconsistency in the DAO governance contract that governs how proposals are created and cancelled. When a user attempts to create a proposal, the contract checks that the user’s prior voting power at the previous block is *strictly greater* than the proposal threshold ( `getPriorVotes(msg.sender, block.number‑1) > proposalThreshold` ). This means that a user who holds exactly the amount of votes required by the threshold is rejected and cannot submit a proposal. Conversely, the cancel function permits any external caller to cancel a proposal only if the proposer’s prior voting power is *strictly less* than the stored proposal threshold ( `getPriorVotes(proposal.proposer, block.number‑1) < proposal.proposalThreshold` ). Because the equality case is excluded from both checks, a proposal that would have been created when the proposer’s votes equal the threshold is impossible to create, yet once such a proposal somehow exists (for example, through a prior implementation or a forked state), it also cannot be cancelled by any other user. The result is a logical dead‑end where a proposal is either never allowed or, if it does appear, becomes uncancellable, breaking the expected lifecycle of governance proposals.

The root cause is the use of mismatched strict inequality operators (> for creation, < for cancellation) without handling the edge case where votes equal the threshold. This off‑by‑one style bug is subtle because typical tests cover clearly above or below the threshold, leaving the exact equality condition unexamined. It was discovered during a manual audit that exercised the proposal flow with voting power precisely at the threshold, revealing that the contract’s revert messages (“proposer votes below proposal threshold” and “proposer above threshold”) are triggered inconsistently.

Exploitation does not require malicious code; an attacker could simply acquire exactly the threshold amount of voting tokens, attempt to create a proposal, be rejected, and then wait for a proposal created under a different condition to reach a state where the proposer’s votes fall to exactly the threshold. At that point, no other participant can cancel the proposal, potentially leading to a denial‑of‑service situation where governance actions are stalled. From a user’s perspective, the symptoms are confusing: a user who believes they have enough votes to propose receives an error, while another user trying to cancel the proposal sees a different error, even though the underlying vote count has not changed. The UI would display a proposal that appears active but offers no cancellation button, contradicting the expectation that proposals can always be revoked by the community when the proposer’s support drops below the required level.

The affected parties include any DAO member whose voting power can equal the proposal threshold, the DAO’s governance process, and any external callers who rely on the ability to cancel stale or malicious proposals. The impact is medium: it does not lead to direct loss of funds, but it can impair the DAO’s ability to manage proposals, potentially causing governance deadlock or unintended persistence of proposals.

To remediate the issue, the contract should adopt a consistent comparison that includes the equality case on both sides of the lifecycle. Either the creation check should be changed to `>= proposalThreshold`, allowing proposers with exactly the threshold to submit proposals, or the cancellation check should be changed to `<= proposalThreshold`, permitting cancellation when votes are equal to the threshold. Importantly, only one of these changes should be applied to avoid creating a scenario where a proposal can be cancelled before it is even allowed to be created. This adjustment aligns the business logic with the intended accounting assumption that meeting the threshold, even exactly, satisfies the eligibility criteria for both creation and cancellation, restoring the expected proposal lifecycle.
