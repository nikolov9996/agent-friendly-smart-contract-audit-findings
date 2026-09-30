---
id: 3300
severity: "High"
---

# Accounts not properly removed from roles upon revoking

## Description

When an account is revoked from a role, _revokeRole function removes account from the members set.
```solidity
function _revokeRole(bytes32 role, address account) internal virtual {
    if (hasRole(role, account)) {
        _roles[role].members.remove(account.toBytes32());
        emit RoleRevoked(role, account, msg.sender);
    }
}
```
In the AsSequentialSet.sol library, roles are stored in the Set struct, which contains an array data and a mapping index from bytes32 to uint32.
```solidity
struct Set {
    bytes32[] data;
    mapping(bytes32 => uint32) index;
}
```
The remove function in the library is supposed to handle the removal of elements but calls removeAt which only removes the account from the Set.data array and does not reset the Set.index.
```solidity
function remove(Set storage q, bytes32 o) internal {
    uint32 i = q.index[o];
    require(i > 0, "Element not found");
    removeAt(q, i - 1);
}

function removeAt(Set storage q, uint256 i) internal {
    require(i < q.data.length, "Index out of bounds");
    if (i < q.data.length - 1) {
        delete q.data[i];
        q.data[i] = q.data[q.data.length - 1];
        q.data.pop();
    }
}
```
Therefore, when the hasRole function checks if a user has a role by using the has function.
```solidity
function hasRole
(bytes32 role, address account) public view virtual returns (bool) {
    return _roles[role].members.has(account.toBytes32());
}
```
And the has function only checks the index of that account, and the index still exists. It means after the user is removed from the role, it still has the role.
```solidity
function has(Set storage q, bytes32 o) internal view returns (bool) {
    return q.index[o] > 0 && q.index[o] <= q.data.length;
}
```
Put the file in test/POC.t.sol https://gist.github.com/thangtranth/685dd8fa7faae141cdd2b1d0061b16f5

## Proof of Concept

No poc.

## Recommendation

The remove function in AsSequentialSet.sol should be modified to reset the index of the removed account
```solidity
function remove(Set storage q, bytes32 o) internal {
    uint32 i = q.index[o];
    q.index[o] = 0;
    require(i > 0, "Element not found");
    removeAt(q, i - 1);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an incomplete removal of an account from a role‑based access control set. When a role is revoked, the internal _revokeRole function calls the remove method of the AsSequentialSet library, which deletes the element from the underlying array but fails to clear the corresponding entry in the index mapping. The hasRole check later reads the index mapping to decide whether an address still holds the role; because the mapping entry remains non‑zero, the contract incorrectly reports that the account still possesses the role even though it has been removed from the array. This inconsistency arises from the removeAt routine only shifting and popping the array element without updating the index, and the has function only validates that the stored index is greater than zero and within the current array length. An attacker who has been revoked can therefore continue to call functions protected by the role modifier, gaining unauthorized access to privileged operations such as fund transfers or configuration changes. The impact is a breach of the intended permission model, potentially allowing theft of assets, manipulation of protocol parameters, or other malicious actions that compromise the security and trust of the system. The flaw manifests whenever a role revocation is performed and the contract later queries the role status, affecting any user whose role is revoked, the protocol’s overall integrity, and any downstream users who rely on correct access control. The issue was discovered during a manual audit of the role management code, where the auditor noticed that the index mapping was never reset after removal, leading to a stale entry that fooled the hasRole view. It can be hard to notice because transaction logs show a RoleRevoked event and the array no longer contains the address, giving the impression that the revocation succeeded, while the contract’s internal state still grants the role. From a user perspective the UI may indicate that the privilege has been removed, yet the user can still execute privileged actions, creating a mismatch between expectation (“I should no longer be able to call admin functions”) and reality (“my calls still succeed”). This class of bug is a typical data‑structure inconsistency where auxiliary bookkeeping structures are not kept in sync after a delete operation, often referred to as a stale mapping or improper set cleanup. The recommended fix is to reset the index entry to zero before calling removeAt, or to replace the custom set implementation with a well‑tested library that atomically updates both the array and the index mapping, ensuring that hasRole returns false after a successful revocation.
