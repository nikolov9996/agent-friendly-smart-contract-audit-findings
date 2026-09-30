---
id: 9260
severity: "High"
---

# activeValidatorCount is never set or increased

## Description

In the NativeVault contract, Storage.ownerToNode[nodeOwner].activeValidatorCount keeps track of the total validators with withdrawal credentials pointed to a specific node. This value is decreased in NativeVaultLib.validateSnapshotProof when the balance of a validator in the Beacon Chain is zero.

File: NativeVaultLib.sol
```solidity
if (newBalanceWei == 0) {
    self.ownerToNode[nodeOwner].activeValidatorCount--;
    validatorDetails.status = ValidatorStatus.WITHDRAWN;
    emit ValidatorWithdrawn(nodeOwner, nodeAddress, timestamp, validatorIndex);
}
```

The value is used in _startSnapshot to set the remainingProofs field of the Snapshot struct.

File: NativeVault.sol
```solidity
NativeVaultLib.Snapshot memory snapshot = NativeVaultLib.Snapshot({
    parentBeaconBlockRoot: _getParentBlockRoot(uint64(block.timestamp)),
    nodeBalanceWei: nodeBalanceWei,
    balanceDeltaWei: 0,
    remainingProofs: node.activeValidatorCount
});
```

However, activeValidatorCount is never set or increased. As a result, remainingProofs will always be initialized to zero, causing the following outcomes:
validateSnapshotProofs will always revert due to underflow error.

File: NativeVault.sol
```solidity
for (uint256 i = 0; i < balanceProofs.length; i++) {
    // ...
    snapshot.remainingProofs--;
    snapshot.balanceDeltaWei += balanceDeltaWei;
}
```

_updateSnapshot will always evaluate to true the condition snapshot.remainingProofs == 0. As a result, node.creditedNodeETH can be updated twice: once on startSnapshot and another called validateSnapshotProofs with an empty balanceProofs array.

File: NativeVault.sol
```solidity
if (snapshot.remainingProofs == 0) {
    int256 totalDeltaWei = int256(snapshot.nodeBalanceWei) + snapshot.balanceDeltaWei;
    node.creditedNodeETH += snapshot.nodeBalanceWei;
    node.lastSnapshotTimestamp = node.currentSnapshotTimestamp;
    delete node.currentSnapshotTimestamp;
    delete node.currentSnapshot;
    _updateBalance(nodeOwner, totalDeltaWei);
    emit SnapshotFinished(
        nodeOwner,
        node.nodeAddress,
        node.lastSnapshotTimestamp,
        totalDeltaWei
    );
} else {
    node.currentSnapshot = snapshot;
}
```

## Proof of Concept

No poc.

## Recommendation

Add the following line in NativeVaultLib.validateWithdrawalCredentials:
```solidity
validatorDetails.status = NativeVaultLib.ValidatorStatus.ACTIVE;
validatorDetails.validatorIndex = validatorFieldsProof.validatorProof.validatorIndex;
validatorDetails.lastBalanceUpdateTimestamp = updateTimestamp;
validatorDetails.restakedBalanceWei = restakedBalanceWei;
self.ownerToNode[nodeOwner].validatorPubkeyHashToDetails[validatorPubkeyHash] = validatorDetails;
self.ownerToNode[nodeOwner].activeValidatorCount++;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the NativeVault contract where the field activeValidatorCount, intended to reflect the number of validators that currently have active withdrawal credentials for a given node, is never initialized or incremented. The contract decreases this counter when a validator balance reaches zero, but because it never starts with a positive value, the counter remains at its default zero. When a snapshot is started, the contract copies activeValidatorCount into the remainingProofs field of the Snapshot struct. Consequently remainingProofs is always zero. The subsequent validation routine iterates over the supplied balance proofs and unconditionally decrements remainingProofs; with an initial value of zero this triggers a Solidity underflow revert. Moreover, the logic that finalizes a snapshot checks if remainingProofs equals zero to decide whether to credit the node’s ETH balance. Since the condition is true immediately, the node’s creditedNodeETH is updated at the start of the snapshot and again when validateSnapshotProofs is called with an empty proof array, resulting in a double credit. From a user perspective the symptoms include unexpected reverts when submitting proofs, the node’s balance appearing to increase twice, or the node’s balance remaining unchanged despite having active validators. The bug affects any node operator or delegator who relies on accurate accounting of validator rewards and withdrawals, potentially leading to loss of funds or over‑payment that must later be corrected. The issue was discovered during a manual security review that traced the flow of activeValidatorCount and noticed the absence of any assignment or increment operation. It is subtle because the counter is stored in a mapping and the contract does not expose it directly, so the problem does not surface until the snapshot logic is exercised. The proper fix is to set activeValidatorCount to one (or increment it) whenever a validator with active withdrawal credentials is added, and to ensure the counter is correctly decremented only when a validator is withdrawn, thereby aligning the remainingProofs value with the actual number of validators that need proof submission. In abstract terms the bug belongs to the class of state‑initialization and counter‑management errors that cause accounting mismatches and premature termination of multi‑step processes.
