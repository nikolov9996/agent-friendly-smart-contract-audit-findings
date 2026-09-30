---
id: 18408
severity: "High"
---

# Self-delgated users can have their delegation unknowingly hijacked during crowdfunding

## Description

Self-delegation can be hijacked.

## Proof of Concept

[PartyGovernance.sol#L886-L906](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/party/PartyGovernance.sol#L886-L906)

```solidity
    function _adjustVotingPower(address voter, int192 votingPower, address delegate) internal {
        VotingPowerSnapshot memory oldSnap = _getLastVotingPowerSnapshotForVoter(voter);
        address oldDelegate = delegationsByVoter[voter];
        // If `oldDelegate` is zero and `voter` never delegated, then have
        // `voter` delegate to themself.
        oldDelegate = oldDelegate == address(0) ? voter : oldDelegate;
        // If the new `delegate` is zero, use the current (old) delegate.
        delegate = delegate == address(0) ? oldDelegate : delegate;

        VotingPowerSnapshot memory newSnap = VotingPowerSnapshot({
            timestamp: uint40(block.timestamp),
            delegatedVotingPower: oldSnap.delegatedVotingPower,
            intrinsicVotingPower: (oldSnap.intrinsicVotingPower.safeCastUint96ToInt192() +
                votingPower).safeCastInt192ToUint96(),
            isDelegated: delegate != voter
        });
        _insertVotingPowerSnapshot(voter, newSnap);
        delegationsByVoter[voter] = delegate;
        // Handle rebalancing delegates.
        _rebalanceDelegates(voter, oldDelegate, delegate, oldSnap, newSnap);
    }
```

Self-delegation is triggered when a user specifies their delegate as address(0). This means that if a user wishes to self-delegate they will can contribute to a crowdfund with delegate == address(0).

[ETHCrowdfundBase.sol#L169-L181](https://github.com/code-423n4/2023-04-party/blob/440aafacb0f15d037594cebc85fd471729bcb6d9/contracts/crowdfund/ETHCrowdfundBase.sol#L169-L181)

```solidity
    function _processContribution(
        address payable contributor,
        address delegate,
        uint96 amount
    ) internal returns (uint96 votingPower) {
        address oldDelegate = delegationsByContributor[contributor];
        if (msg.sender == contributor || oldDelegate == address(0)) {
            // Update delegate.
            delegationsByContributor[contributor] = delegate;
        } else {
            // Prevent changing another's delegate if already delegated.
            delegate = oldDelegate;
        }
```

This method of self-delegation is problematic when combined with `_processContribution`. When contributing for someone else, the caller is allowed to specify any delegate they wish. If that user is currently self delegated, then the newly specified delegate will overwrite their self delegation. This allows anyone to hijack the voting power of a self-delegated user.

This can create serious issues for ReraiseETHCrowdfund because party NFTs are not minted until after the entire crowdfund is successful. Unlike InitialETHCrowdfund, this allows the attacker to hijack all of the user’s newly minted votes.

**Example:**  
`minContribution = 1` and `maxContribution = 100`. User A contributes 100 to ReraiseETHCrowdfund. They wish to self-delegate so they call contribute with delegate == address(0). An attacker now contributes 1 on behalf of User A with themselves as the delegate. Now when the NFTs are claimed, they will be delegated to the attacker.

## Recommendation

Self-delegation should be automatically hardcoded:

```solidity
    if (msg.sender == contributor && delegate == address(0)) {
        delegationsByContributor[contributor] = contributor;
    }

    address oldDelegate = delegationsByContributor[contributor];
    if (msg.sender == contributor || oldDelegate == address(0)) {
        // Update delegate.
        delegationsByContributor[contributor] = delegate;
    } else {
        // Prevent changing another's delegate if already delegated.
        delegate = oldDelegate;
    }
```

This appears valid at first pass and allows anyone to steal self delegations.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is an unintended delegation hijack that occurs when a contributor who has self‑delegated (by passing address(0) as the delegate) is later funded by a third party. The contract stores a delegationsByContributor entry that is initialised to address(0) for self‑delegation. In the internal _processContribution function the code checks "if (msg.sender == contributor || oldDelegate == address(0))" before updating the delegate. Because oldDelegate is zero for a self‑delegated user, the condition is true even when the caller is not the contributor. Consequently, an attacker who calls contribute on behalf of the victim can supply any delegate address, and the contract overwrites the victim’s self‑delegation with the attacker’s address. The root cause is the use of address(0) as both a sentinel for “no delegate” and as the signal for self‑delegation, combined with a permissive update rule that does not distinguish between a genuine owner‑initiated change and a third‑party contribution. Exploitation is straightforward: the attacker simply makes a minimal contribution for the target user, specifying their own address as the delegate. The impact is that the victim’s voting power, which would normally be attached to their own address or to a chosen delegate, is transferred to the attacker. In the ReraiseETHCrowdfund scenario, where party NFTs (and thus voting rights) are minted only after the crowdfund succeeds, the attacker can capture all of the newly minted votes, effectively stealing the user’s influence in the governance process. This bug is discovered during a security audit that examined the delegation logic and contribution flow. It can be hard to notice because the code appears to protect existing delegations by checking for a non‑zero oldDelegate, yet self‑delegation also results in a zero value, unintentionally satisfying the same condition. From a user’s perspective the symptom is that after contributing with delegate set to zero, the user later finds that their NFTs are delegated to an unknown address, or that they receive no voting power despite having contributed the maximum amount. The expected behaviour is that a self‑delegated user retains control over their own votes, but the reality is that an attacker can hijack those votes. The vulnerability belongs to the class of delegation‑overwrite or authority‑confusion bugs, where a sentinel value is misinterpreted, allowing unauthorized state changes. To remediate, the contract should hard‑code self‑delegation by setting the delegate to the contributor’s own address when the supplied delegate is zero, and should reject delegate updates from callers that are not the contributor unless the existing delegate is already non‑zero, thereby preventing third‑party contributions from overwriting a self‑delegated entry.
