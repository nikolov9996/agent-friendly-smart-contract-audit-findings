---
id: 15648
severity: "High"
---

# Missing check on toBlock allows distributors to change past rewards

## Description

The function commit in DistributedRewardDistribution.sol is used to save a reward commit. However this function does not check if the toBlock is larger than the fromBlock. Thus distributors can set toBlock to 0 even.

```solidity
require(
    recipients.length == workerRewards.length,
    "Recipients and worker amounts length mismatch"
);
require(
    recipients.length == _stakerRewards.length,
    "Recipients and staker amounts length mismatch"
);
require(currentDistributor() == msg.sender, "Not a distributor");
//@audit missing check on block span
require(toBlock < block.number, "Future block");
```

This creates further problems in the distribute function itself. There is a check there which tries to force distributions to be sequential.

```solidity
require(
    lastBlockRewarded == 0 || fromBlock == lastBlockRewarded + 1,
    "Not all blocks covered"
);
```

However, an user can set the toBlock to be lower than the fromBlock and this will break the sequence. In fact, if a user sets toBlock to 0, they can even set lastBlockRewarded to 0 since the assignment takes place in the next line.

```solidity
lastBlockRewarded = toBlock;
```

The test test_RunsDistributionAfter3Approves can be modified with the blockspan running from 1 to 0 to demonstrate the issue.

```solidity
function test_RunsDistributionAfter3Approves() public {
    uint256[] memory recipients,
    uint256[] memory workerAmounts,
    uint256[] memory stakerAmounts
) = prepareRewards(1);
rewardsDistribution.addDistributor(address(1));
rewardsDistribution.addDistributor(address(2));
rewardsDistribution.setApprovesRequired(3);
vm.roll(10);
rewardsDistribution.commit(
    recipients,
    workerAmounts,
    stakerAmounts
);
hoax(address(1));
rewardsDistribution.approve(
    recipients,
    workerAmounts,
    stakerAmounts
);
hoax(address(2));
rewardsDistribution.approve(
    recipients,
    workerAmounts,
    stakerAmounts
);
```

Test passes with no issues.

## Proof of Concept

No poc.

## Recommendation

Enforce the check

```solidity
require(toBlock > fromBlock, "Invalid block span");
```

Either in the commit function or in the distribute function.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an absent validation of the block interval supplied to the reward‑commit function of a distributed reward contract. Specifically, the function that records a reward commitment accepts a fromBlock and a toBlock but only checks that toBlock is not in the future; it does not enforce that toBlock is greater than fromBlock. Because of this missing check, a distributor can submit a commitment where toBlock is equal to zero or any value lower than fromBlock. When such a malformed commitment is later processed by the distribute routine, the contract’s sequential‑block invariant – which expects each distribution to start exactly one block after the previous lastBlockRewarded – is broken. The distribute function contains a guard that requires either that no previous distribution exists (lastBlockRewarded == 0) or that the new fromBlock equals lastBlockRewarded + 1. By setting toBlock to a lower value, the attacker can also set lastBlockRewarded to that lower value in the same transaction, effectively resetting the progression counter to zero. This enables the attacker to claim rewards for blocks that have already been accounted for, to re‑enter the distribution window for past periods, or to cause the contract to skip forward and later distribute extra rewards that were never intended. The impact is a breach of the accounting assumptions of the protocol: funds may be paid out multiple times, some participants may receive no reward while others receive more than their share, and the overall reward schedule becomes inconsistent, potentially draining the contract’s balance. The flaw manifests whenever a distributor calls commit with a malicious block span; it does not require any special blockchain state beyond the ability to submit a transaction. All parties that rely on the contract for fair reward distribution – stakers, workers, and the protocol itself – are affected because the reward accounting can be corrupted. The issue was discovered during a manual audit that inspected the require statements in the commit function and noticed the absence of a check that toBlock > fromBlock, and then traced the effect through the sequential check in distribute. It can be hard to notice because the contract still passes existing unit tests; the test suite does not include a case where fromBlock exceeds toBlock, so the bug remains hidden under normal test conditions. The appropriate remediation is to enforce a strict block‑span validation, for example by requiring toBlock > fromBlock (or at least toBlock >= fromBlock + 1) either in the commit function or directly before updating lastBlockRewarded. This restores the invariant that reward periods are monotonic and non‑overlapping, preventing distributors from resetting or shrinking the reward window. In generic terms, the bug belongs to the class of missing input validation leading to state‑invariant violations, where an unchecked parameter allows an attacker to manipulate the progression of a time‑based accounting variable. From a user’s perspective the symptom may appear as rewards disappearing, duplicate payouts, or a balance that unexpectedly drops to zero after a commit, contrary to the expectation that rewards are accrued continuously and sequentially.
