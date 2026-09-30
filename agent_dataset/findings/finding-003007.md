---
id: 3007
severity: "High"
---

# Attacker can remove voting power from more than 52 minutes ago due to maximum queue length

## Description

The voting power queue of each user has a maximum length of MAX_HISTORY_LENGTH. In the current implementation, the queue can have a maximum length of 256:
```solidity
// Max length of any voting history. Prevents gas exhaustion
// attacks from having too-large history.
uint256 public constant MAX_HISTORY_LENGTH = 256;
```
For example, when pushing a new checkpoint into the voting power queue in changeDelegation(), MAX_HISTORY_LENGTH is passed to push():
```solidity
// Store the increase in power
votingPower.push(newDelegate, newDelegateVotes + userBalance, MAX_HISTORY_LENGTH);
```
In BoundedHistory.push(), a new checkpoint with the current block number is added to the front of the queue. Afterwards, if the queue's new length exceeds 256, the oldest checkpoint is deleted from the back of the queue:
```solidity
} else if (length - minIndex >= maxLength) {
    // We need to push to the array, but if array is full to maxLength, so
    // we clear the oldest entry and increment the minIndex
    _clear(minIndex, ++minIndex, storageData);
}
```
However, such an implementation allows an attacker to force a user's history to only store the last MAX_HISTORY_LENGTH blocks. Since the maximum queue length is 256 in the current implementation, an attacker can force the contract to only store a user's voting power history for the last 256 blocks. This can be achieved by:
- At every block, call changeDelegation() with newDelegate set to the victim's address. This will push a new entry into votingPower for the current block number.
- Due to the 256-entry limit for votingPower, after changeDelegation() is called enough times for votingPower to hold more than 256 entries, push() will start to delete the oldest entry.
- After 256 blocks, all past entries in votingPower will have been deleted, so the oldest entry will be from 256 blocks ago.
If queryVotePower() is called to query a user's voting power more than 256 blocks ago, the function will revert as there is no record of the user's voting power before or during blockNumber.
Since mainnet produces a block every 12 seconds, 256 blocks corresponds to 51.2 minutes, which means an attacker can forcefully remove a victim's voting power history from more than ~52 minutes ago.
Note that deposit() and withdraw() can also be used to perform the same attack, since they also add checkpoints to the delegate's queue with _addVotingPower() and _subtractVotingPower().

## Proof of Concept

no poc

## Recommendation

Consider removing the MAX_HISTORY_LENGTH limit on the checkpoint queue (i.e. the queue can be infinitely long). This can be achieved by setting MAX_HISTORY_LENGTH to an extremely large value, such as type(uint256).max, or reverting the contract to use History instead of BoundedHistory.
To prevent the issue of queryVotePower() running out of gas when the queue is too long, avoid clearing stale blocks in the queue when queryVotePower() is called:
```solidity
function queryVotePower(
    address user,
    uint256 blockNumber,
    bytes calldata
) external override returns (uint256) {
    // Get our reference to historical data
    BoundedHistory.HistoricalBalances memory votingPower = _votingPower();
    // Find the historical data and clear everything more than 'staleBlockLag' into the past
    return
        votingPower.findAndClear(
            user,
            blockNumber,
            block.number - STALE_BLOCK_LAG
        );
    return this.queryVotePowerView(user, blockNumber);
}
```
This would be similar to other implementations of voting checkpoint queues, such as OpenZeppelin's Votes.sol, which only adds checkpoints to the queue and but never removes them.
The only functions remaining that iterate through the checkpoint queue would be queryVotePower() and queryVotePowerView(), which performs a maximum of log(n) iterations using binary search.
Therefore, there isn't a need to remove stale checkpoints from the queue as there is no risk of any function ever running out-of-gas, resulting in DOS.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a history‑truncation flaw in the voting power checkpoint queue. The contract stores each change of a user’s voting power in a bounded array whose maximum length is defined by MAX_HISTORY_LENGTH, currently set to 256 entries. When a new checkpoint is pushed and the array is already full, the oldest entry is removed from the back of the queue. Because the queue can hold only the most recent 256 blocks, any record older than roughly 256 × 12 seconds (about 52 minutes) is discarded. An attacker who can submit a transaction every block can repeatedly call changeDelegation (or deposit or withdraw) with the victim’s address as the delegate. Each call creates a new checkpoint for the current block, pushing the queue toward its limit. After 256 such calls, the oldest checkpoint corresponds to the block 256 blocks ago, and all earlier history has been erased. When the protocol or a user later calls queryVotePower for a block earlier than the retained window, the function reverts because the required checkpoint no longer exists. From the user’s perspective the UI may show an error, return zero, or simply fail when trying to display voting power from a past block, contradicting the expectation that any historical voting power can be queried. The issue affects any participant whose voting power is queried for older blocks, as well as the governance logic that relies on accurate historical balances. It was discovered during a security audit by inspecting the BoundedHistory.push implementation and noticing the automatic deletion of the oldest entry once the length exceeds MAX_HISTORY_LENGTH. The problem is subtle because normal operation for recent blocks works correctly, and the loss of older data may only be observed when a governance query targets a block outside the retained window. The bug belongs to the class of bounded checkpoint queue vulnerabilities that cause history truncation and denial‑of‑service for historical queries. The recommended remediation is to remove the hard limit on the checkpoint array, for example by setting MAX_HISTORY_LENGTH to the maximum uint256 value or by switching to an unbounded history structure such as OpenZeppelin’s Votes implementation. This eliminates the need to clear stale entries and ensures that queryVotePower can always retrieve any past voting power using binary search without risking out‑of‑gas errors.
