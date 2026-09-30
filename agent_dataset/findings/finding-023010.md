---
id: 23010
severity: "High"
---

# Voters will lose all bribe rewards forever if they

## Description

The claim() function in BribeRewarder is used to claim the rewards associated with a tokenID across all bribe periods that have ended: it iterates over all the voting periods starting from the bribe rewarder's _startVotingPeriod up to the last period that ended according to the Voter.sol contract, and collects and sends rewards to the NFT's owner.
The issue is that if the voter (i.e. tokenID owner who earned bribe rewards for one or more bribe periods) does not claim his rewards by the lastVotingPeriod + 2, then all his unclaimed rewards for all periods will be lost forever.
Let's walk through an example to better understand the issue. Even though the issue occurs in all other cases, we are assuming that the voting period has just started to make it easy to understand.
1. The first voting period is about to start in the next block. The bribe provider deploys a bribe rewarder and registers it for a pool X for voting periods 1 to 5. i.e. the startVotingPeriod in the BribeRewarder.sol = 1 and lastVotingPeriod = 5.
2. The first voting period starts in voter.sol. Users start voting for pool X and the BribeRewarder keeps getting notified and storing the rewards data in respective rewarder data structure (see here and here)
3. All 5 voting periods have ended. User voted in all voting periods and got a reward stored for all 5 bribe periods in the BribeRewarder contract. Now when he claims via claim(), he can get all his rewards.
4. Assume that the 6th voting period has ended. Still if the user calls claim(), he will get back all his rewards. His 6th period rewards will be empty but it does not revert.
5. Assume that the 7th voting period has ended. Now if the user calls claim(), his call will revert and from now on, he will never be able to claim any of his unclaimed rewards for all periods.

The reason of this issue is this:
```solidity
function claim(uint256 tokenId) external override {
    uint256 endPeriod = IVoter(_caller).getLatestFinishedPeriod();
    uint256 totalAmount;
    for (uint256 i = _startVotingPeriod; i <= endPeriod; ++i) {
        totalAmount += _modify(i, tokenId, 0, true);
    }
    emit Claimed(tokenId, _pool(), totalAmount);
}
```
The claim function is the only way to claim a user's rewards after he has voted. This iterates over the voting periods starting from the _startVotingPeriod (which is equal to 1 in our example).
This loop's last iteration is the latest voting period that might have ended on the voter contract (regardless of if it was declared as a bribe period in our own BribeRewarder since voting periods will be a forever going thing and we only want to reward up to a limited set of periods, defined by BribeRewarder:_lastVotingPeriod).

Let's see the Voter.getLatestFinishedPeriod() function:
```solidity
function getLatestFinishedPeriod() external view override returns (uint256) {
    if (_votingEnded()) {
        return _currentVotingPeriodId;
    }
    if (_currentVotingPeriodId == 0) revert IVoter__NoFinishedPeriod();
    return _currentVotingPeriodId - 1;
}
```
Now if suppose the 6th voting period is running, it will return 5 as finished. if 7th is running, it will return 6, and if 8th period has started, it will return 7.

Now back to claim => _modify. It fetches the rewards data for that period in the _rewards array, which has (lastID - startID) + 2 elements. (see here). In our case, this array will consist of 6 elements (startId = 1 and lastID = 5).

Now when we see how it is fetching the reward data using periodID, it is using the value returned by _indexByPeriodId() as the index of the array.
```solidity
function _indexByPeriodId(uint256 periodId) internal view returns (uint256) {
    return periodId - _startVotingPeriod;
}
```
So for a periodID = 7, this will return index 6.

Now back to the example above. When the 7th voting period has ended, getLatestFinishedPeriod() will return 7 and the claim function will try to iterate over all the periods that have ended. When the iteration comes to this last period = 7, the _modify function will try to read the array element at index 6 (again we can see this clearly here)
But now it will revert with index out of bounds, because the array only has 6 elements from index 0 to index 5, so trying to access index element 6 in _rewards array will now always revert.

This means that after 2 periods have passed after the last bribing period, no user can ever claim any of their rewards even if they voted for all the periods.
No user will be able to claim any of their unclaimed rewards for any periods from the BribeRewarder, after this time. The rewards will be lost forever, and a side effect of this is that these rewards will remain stuck in the BribeRewarder. But the main impact is the complete loss of rewards of many users.
High severity because users should always get their deserved rewards, and many users could lose rewards this way at the same time. The damage to the individual user depends on how many periods they didn't claim for and how much amount they used for voting, which could be a very large amount.

## Proof of Concept

no poc

## Recommendation

The solution is simple: in the claim function, limit the endPeriod used in the loop by the _lastVotingPeriod of a particular BribeRewarder.
```solidity
uint256 endPeriod = IVoter(_caller).getLatestFinishedPeriod();
if (endPeriod > _lastVotingPeriod) endPeriod = _lastVotingPeriod;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an out‑of‑bounds array access in the reward‑claiming routine of a bribe‑reward contract. The contract stores a fixed‑size rewards array that is sized only for the periods that were originally advertised as bribe periods (for example periods 1‑5). The claim() function determines the last finished voting period by calling Voter.getLatestFinishedPeriod() and then iterates from the contract’s _startVotingPeriod up to that value, summing the rewards for each period. Because the loop does not cap the iteration at the contract’s own _lastVotingPeriod, once two voting periods have elapsed after the final advertised bribe period, the loop reaches a period identifier that has no corresponding entry in the rewards array. The internal index calculation (periodId‑_startVotingPeriod) then produces an index that is equal to the length of the array, causing a Solidity index out of bounds revert. The revert aborts the whole claim transaction, so any rewards that were still unclaimed for earlier periods become permanently inaccessible. From a user’s perspective the contract silently accepts a claim call, but after the seventh voting period the transaction reverts and the user receives no tokens, even though the UI may still show a non‑zero pending reward balance. The issue is triggered only after the blockchain advances past the last bribe period plus two additional voting cycles, which can be hard to notice because the contract continues to work correctly for the first two periods after the advertised end. The bug belongs to the class of incorrect loop bounds leading to array‑index overflow and violates the accounting assumption that the reward data structure contains an entry for every period the claim loop may address. It was discovered during a manual audit of the BribeRewarder contract when the auditor examined the interaction between the claim loop and the Voter contract’s period calculation. The problem may remain hidden in production because the revert only occurs after a delay, and users may assume that a failed claim is a temporary network issue rather than a permanent loss of funds. The proper fix is to constrain the loop’s endPeriod to the contract’s own _lastVotingPeriod, ensuring that the loop never accesses an index beyond the allocated rewards array. By adding a simple min‑check (if endPeriod > _lastVotingPeriod then endPeriod = _lastVotingPeriod) the contract will stop iterating over non‑existent periods, allowing users to claim all accrued rewards at any time before the final period ends.
