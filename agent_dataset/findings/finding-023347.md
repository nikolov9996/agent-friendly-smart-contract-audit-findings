---
id: 23347
severity: "High"
---

# New users can'tbe registered after slashing contrary to documentation

## Description

RLN.sol has variable `SET_SIZE`, which defines maximum number of registered users. During slashing, users are deleted from registry:

```solidity
function slash(bytes32 privateKey, address rewardRecipient) private onlyRole(SLASHER_ROLE) {
    // Hash the private key using Poseidon to get identityCommitment
    uint256 identityCommitment = poseidonHasher.hash(uint256(privateKey));
    User memory member = members[identityCommitment];
    if (member.userAddress == address(0)) {
        revert RLN__MemberNotFound();
    }
    karma.slash(member.userAddress, rewardRecipient);
    @> delete members[identityCommitment];
}
```

According to documentation https://github.com/status-im/status-network-monorepo/blob/develop/status-network-contracts/docs/rln.md#registry-capacity:

> Once the registry reaches capacity, new registrations are rejected until space is available. When accounts are slashed, their identity commitments are removed from the registry, freeing up space for new registrations.

However slashing accounts doesn't free up space for new registrations:

```solidity
function register(uint256 identityCommitment, address user) external onlyRole(REGISTER_ROLE) {
    @> uint256 index = identityCommitmentIndex;
    @> if (index >= SET_SIZE) {
        revert RLN__SetIsFull();
    }
    if (members[identityCommitment].userAddress != address(0)) {
        revert RLN__IdCommitmentAlreadyRegistered();
    }
    /// forge-lint: disable-next-line(named-struct-fields)
    members[identityCommitment] = User(user, index);
    emit MemberRegistered(identityCommitment, index);
    unchecked {
        @> identityCommitmentIndex = index + 1;
    }
}
```

Impact: New users can't be registered after slashing contrary to documentation.

## Proof of Concept

```solidity
function slash(bytes32 privateKey, address rewardRecipient) private onlyRole(SLASHER_ROLE) {
    // Hash the private key using Poseidon to get identityCommitment
    uint256 identityCommitment = poseidonHasher.hash(uint256(privateKey));
    User memory member = members[identityCommitment];
    if (member.userAddress == address(0)) {
        revert RLN__MemberNotFound();
    }
    karma.slash(member.userAddress, rewardRecipient);
    @> delete members[identityCommitment];
}
```

```solidity
function register(uint256 identityCommitment, address user) external onlyRole(REGISTER_ROLE) {
    @> uint256 index = identityCommitmentIndex;
    @> if (index >= SET_SIZE) {
        revert RLN__SetIsFull();
    }
    if (members[identityCommitment].userAddress != address(0)) {
        revert RLN__IdCommitmentAlreadyRegistered();
    }
    /// forge-lint: disable-next-line(named-struct-fields)
    members[identityCommitment] = User(user, index);
    emit MemberRegistered(identityCommitment, index);
    unchecked {
        @> identityCommitmentIndex = index + 1;
    }
}
```

## Recommendation

Add missing feature or update documentation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the registration capacity management in the RLN contract. The contract defines a constant SET_SIZE that limits the number of identity commitments that can be stored. When a user is slashed, the slash function deletes the member entry from the members mapping, which according to the documentation should free a slot for new registrations. However, the register function determines whether space is available by comparing a monotonically increasing counter, identityCommitmentIndex, against SET_SIZE. This counter is incremented on each successful registration but never decremented or otherwise updated when a member is removed. As a result, once the counter reaches the maximum, the condition index >= SET_SIZE remains true even after entries have been deleted, causing every subsequent registration attempt to revert with RLN__SetIsFull. The root cause is a mismatch between the logical expectation that deleting a member frees capacity and the actual implementation that tracks capacity with an immutable index. Exploitation is straightforward: an attacker can fill the registry up to SET_SIZE, then either slash existing members or wait for legitimate slashing events, yet new users will still be unable to register because the capacity check does not reflect the freed slots. This leads to a denial‑of‑service scenario where onboarding of new participants is blocked, reducing the effective anonymity set and potentially weakening the privacy guarantees of the protocol. The issue manifests when the registry is full and any further registration is attempted, regardless of prior slashing activity. Affected parties include any user trying to join the network, the protocol’s governance that relies on a dynamic participant pool, and developers who assume the documented behavior. The bug was discovered during an audit that compared the contract’s behavior against its public documentation, revealing that the slashing operation does not actually reclaim space. The problem is subtle because the delete operation appears to remove data, giving the impression that capacity is restored, while the separate index variable silently prevents new entries. To remediate, the contract should either decrement the index when a member is removed, maintain a free‑slot list that can be reused, or redesign the capacity tracking to reflect the actual number of active entries. Updating the documentation to accurately describe the implemented behavior is also necessary to avoid misleading users.
