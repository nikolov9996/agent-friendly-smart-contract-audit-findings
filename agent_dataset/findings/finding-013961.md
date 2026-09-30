---
id: 13961
severity: "High"
---

# Calling validateWithdrawalCredentials() followed by startSnapshot()/validateExpiredSnapshot() will permanently DOS snapshots

## Description

NativeVaultLib.validateWithdrawalCredentials() has the following checks for beaconStateRootProof.timestamp:
```solidity
if (
beaconStateRootProof.timestamp < node.lastSnapshotTimestamp
|| beaconStateRootProof.timestamp < node.currentSnapshotTimestamp
) revert BeaconTimestampTooOld();
```
As seen from above, only restriction on beaconStateRootProof.timestamp is that it cannot be older than the last/ongoing snapshot. This makes it possible for beaconStateRootProof.timestamp to be block.timestamp.
Later on in the function, the newly added validator's lastBalanceUpdateTimestamp is set to beaconStateRootProof.timestamp in NativeVaultLib.validateWithdrawalCredentials():
```solidity
validatorDetails.lastBalanceUpdateTimestamp = updateTimestamp;
```
However, if startSnapshot() or validateExpiredSnapshot() is called after validateWithdrawalCredentials() in the same block, the newly added validator cannot be proven with validateSnapshotProofs() due to the following check:
```solidity
if (validatorDetails.lastBalanceUpdateTimestamp >= node.currentSnapshotTimestamp) {
revert ValidatorAlreadyProved();
}
```
This will make it impossible to complete the snapshot as the newly added validator can never be proven, so snapshot.remainingProofs will never reach 0. For example:
• Assume a node owner has no validators.
• In the block where block.timestamp = 1000:
– validateWithdrawalCredentials() is called:
* Assume beaconStateRootProof.timestamp = block.timestamp.
* validator.lastBalanceUpdateTimestamp = 1000.
* node.activeValidatorCount is incremented to 1.
– startSnapshot() is called to start a new snapshot:
* snapshot.remainingProofs = 1
* node.currentSnapshotTimestamp = 1000
• When attempting to prove the validator with validateSnapshotProofs():
– Both validatorDetails.lastBalanceUpdateTimestamp and node.currentSnapshotTimestamp are 1000, so the check shown above reverts.
• As such, the validator can never be proven and snapshot.remainingProofs is forever stuck at 1.
If this occurs, snapshots will be forever DOSed for the node owner.

## Proof of Concept

no poc

## Recommendation

Ensure that validateWithdrawalCredentials() cannot be called with beaconStateRootProof.timestamp as block.timestamp by adding the following check:
```solidity
if (beaconStateRootProof.timestamp == block.timestamp) {
revert BeaconTimestampIsCurrent();
}
```
Note that even without this check, it is unlikely for validateWithdrawalCredentials() to be called with block.timestamp as it is difficult to generate proofs for a block root returned by _getParentBlockRoot() in a future block.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical timestamp validation flaw that allows a node owner to permanently deny service to snapshot finalisation. The contract function that validates withdrawal credentials only checks that the supplied beaconStateRootProof.timestamp is not older than the last or current snapshot timestamps, but it does not forbid the timestamp from being exactly equal to the current block timestamp. When validateWithdrawalCredentials is called with a timestamp equal to block.timestamp, the newly added validator’s lastBalanceUpdateTimestamp is set to that same value. If startSnapshot or validateExpiredSnapshot is invoked later in the same block, the node’s currentSnapshotTimestamp is also set to block.timestamp. The later proof verification function contains a guard that reverts if validatorDetails.lastBalanceUpdateTimestamp is greater than or equal to node.currentSnapshotTimestamp, triggering a ValidatorAlreadyProved revert. Because the timestamps are identical, the validator can never be proven, leaving snapshot.remainingProofs stuck at a non‑zero value forever. This condition occurs only when the two functions are executed within the same block and the timestamp supplied matches the block timestamp. The affected parties are node owners and any participants relying on snapshots for reward distribution or accounting, as the snapshot can never reach completion and funds associated with the validator remain locked. The issue was discovered during a security audit by analysing the timestamp checks and the invariant that snapshot.remainingProofs must eventually reach zero. It is hard to notice because the contract behaves correctly under normal timing, and the failure only appears when the edge case of equal timestamps is exercised, causing a silent stall rather than an immediate error. The bug belongs to the class of state‑locking denial‑of‑service vulnerabilities caused by insufficient input validation. From a user perspective the UI would show a pending snapshot that never finalises, the validator appears active but cannot be claimed, and expected rewards are not received. The recommended remediation is to add an explicit check that rejects a beaconStateRootProof.timestamp equal to block.timestamp, or to require the timestamp to be strictly less than the current snapshot timestamp, thereby preventing the invariant violation that leads to the permanent DOS condition.
