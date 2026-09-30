---
id: 14958
severity: "High"
---

# Upon changing of delegate, `VoteDelegation` updates both the previous and the current checkpoint

## Description

The contract is accidently editing both the previous and current checkpoint when changing/removing a delegate.

## Proof of Concept

If in `delegate` the delegate already has checkpoints, the function will grab the latest checkpoint, and add the `tokenId` to it. Note that it changes the storage variable.
```solidity
if (nCheckpoints > 0) {
    Checkpoint storage checkpoint = checkpoints[toTokenId][nCheckpoints - 1];
    checkpoint.delegatedTokenIds.push(tokenId);
    _writeCheckpoint(toTokenId, nCheckpoints, checkpoint.delegatedTokenIds);
```
It then calls `_writeCheckpoint`, which [will add](https://github.com/code-423n4/2022-07-golom/blob/main/contracts/vote-escrow/VoteEscrowDelegation.sol#L106) a new checkpoint if there’s no checkpoint created for this block yet:
```solidity
Checkpoint memory oldCheckpoint = checkpoints[toTokenId][nCheckpoints - 1];

if (nCheckpoints > 0 && oldCheckpoint.fromBlock == block.number) {
    oldCheckpoint.delegatedTokenIds = _delegatedTokenIds;
} else {
    checkpoints[toTokenId][nCheckpoints] = Checkpoint(block.number, _delegatedTokenIds);
    numCheckpoints[toTokenId] = nCheckpoints + 1;
}
```
Therefore, if this function has created a new checkpoint with the passed `_delegatedTokenIds`, we already saw that the previous function has already added `tokenId` to the previous checkpoint, so now both the new checkpoint and the previous checkpoint will have `tokenId` in them.  
This is wrong as it updates an earlier checkpoint with the latest change.

The same situation happens in [`removeDelegation`](https://github.com/code-423n4/2022-07-golom/blob/main/contracts/vote-escrow/VoteEscrowDelegation.sol#L213).

## Recommendation

When reading the latest checkpoint:
```solidity
Checkpoint storage checkpoint = checkpoints[toTokenId][nCheckpoints - 1];
```
Change the `storage` to `memory`. This way it will not affect the previous checkpoint, but will pass the correct updated array to `_writeCheckpoint`, which will then write/update the correct checkpoint.

Fixed `delegate()`: <https://github.com/golom-protocol/contracts/commit/8a8c89beea22cd57f4ffaf3d0defcce863e9657f>

Fixed `removeDelegation()`: <https://github.com/golom-protocol/contracts/commit/72350b0a3bdae4f21e2f015327037080f6bab867>

I went back and forth on if this was a duplicate of [H-04 (#169)](https://github.com/code-423n4/2022-07-golom-findings/issues/169) or not. The two issues are so similar it’s hard to pull them apart. Ultimately I do see the difference, mainly that this version of the issue results in a retroactive manipulation of voting power whereas the other issue allows the creation of infinite voting power. I’m upgrading this to high risk because it effectively destroys the integrity of the voting system which impacts every aspect of the protocol which is subject to vote.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the vote‑delegation logic of the contract that tracks voting power through a series of checkpoints. When a token holder changes or removes a delegate, the implementation reads the most recent checkpoint using a storage reference, mutates that checkpoint by adding or removing a token ID, and then forwards the modified structure to the internal `_writeCheckpoint` routine. Because the checkpoint was obtained as a storage pointer, the mutation also alters the historic checkpoint that should remain immutable. `_writeCheckpoint` subsequently creates a new checkpoint for the current block, copying the already‑modified token list, which means that both the previous checkpoint and the newly created one now contain the same token ID. The root cause is the misuse of a `storage` variable where a `memory` copy should be used, causing retroactive modification of past voting power records. An attacker who controls delegation can therefore inflate their voting power for earlier blocks, effectively rewriting the voting history. This manipulation can change the outcome of past governance proposals, corrupt quorum calculations, and undermine the integrity of any protocol component that relies on the historical voting snapshot. The flaw manifests whenever a delegate is assigned to an address that already holds one or more checkpoints, or when an existing delegation is removed, because both paths read and mutate the latest checkpoint in storage. All token holders and the governance process are affected, as the voting power of delegates may be reported incorrectly. The issue was discovered during a manual security audit that inspected the delegation flow and observed that the same token ID appeared in both the old and new checkpoint after a delegation change. It is subtle because checkpoints are internal data structures not directly exposed to users; the bug does not produce an immediate runtime error, but the resulting vote tallies are silently wrong, making it difficult to detect without deep inspection of the checkpoint history. To remediate the problem, the contract should retrieve the latest checkpoint into a temporary `memory` variable, modify that copy, and then write the updated data to a new checkpoint, ensuring that historic checkpoints remain unchanged. In abstract terms, the bug belongs to the class of state‑mutation‑through‑aliasing errors, where a reference to persistent storage is unintentionally altered, leading to retroactive state corruption. From a user’s perspective, a delegator may notice that their voting power appears higher than expected for previous periods, or that proposals they did not vote on seem to have been decided differently, contrary to the expectation that delegation only affects future votes. This breach of accounting assumptions violates the core business rule that voting power snapshots must be immutable once recorded.
