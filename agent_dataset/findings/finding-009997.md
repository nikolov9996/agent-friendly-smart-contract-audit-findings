---
id: 9997
severity: "High"
---

# Soulbound checks and _manageIndexes() can be bypassed by specifying duplicate key IDs in ids

## Description

Users who have more keys for a certain key ID than soulboundKeyAmounts can transfer all their keys to another address. Additionally, addressKeys and keyHolders will contain key IDs and addresses respectively that should have been removed after a transfer.

The _update() function enforces soulbound checks for users by ensuring that the remaining balance after the transfer is not less than soulboundKeyAmounts for each ID in ids:
```solidity
for(uint256 x = 0; x < ids.length; x++) {
    // we need to allow address zero during minting,
    // and we need to allow the locksmith to violate during burning
    if ( (from != address(0)) && (to != address(0)) && (balanceOf(from, ids[x]) - values[x]) < soulboundKeyAmounts[from][ids[x]]) {
        revert SoulboundTransferBreach();
    }
```
However, this check can be bypassed by specifying duplicate key IDs in ids. For example:
• Alice has two keys of id = 1.
• soulboundKeyAmounts[alice][1] = 1, which means that one of Alice's keys should not be transferable.
• Alice calls safeBatchTransferFrom() with:
– ids = [1, 1]
– values = [1, 1]
– The check above passes as balanceOf(alice, ids[x]) - values[x] = 1 for all x in ids.
– Therefore, both of Alice's keys are transferred to another address.
Similarly, _manageIndexes() removes from addressKeys and keyHolders under the following condition:
```solidity
// lets keep track of each key that is moving
if(balanceOf(from, id) == value) {
    addressKeys[from].remove(id);
    keyHolders[id].remove(from);
}
```
However, if ids contains duplicate key IDs as shown in the example above, balanceOf() will not be equal to value. Therefore, addressKeys and keyHolders will not be updated even when the user has transferred all his keys.

## Proof of Concept

no poc

## Recommendation

In _update(), consider ensuring that ids does not contain duplicate key IDs:
```solidity
for(uint256 x = 0; x < ids.length; x++) {
    for (uint256 y = 0; y < x; y++) {
        if (ids[x] == ids[y]) {
            revert DuplicateKeyID();
        }
    }
    // we need to allow address zero during minting,
    // and we need to allow the locksmith to violate during burning
    if ( (from != address(0)) && (to != address(0)) && (balanceOf(from, ids[x]) - values[x]) < soulboundKeyAmounts[from][ids[x]]) {
        revert SoulboundTransferBreach();
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical bypass of the soulbound key transfer restriction and the index‑maintenance routine in a multi‑token contract that tracks ownership of distinct key IDs. The contract is supposed to prevent a user from transferring away a number of keys that are marked as soulbound by checking, for each ID in the batch, that the remaining balance after the transfer does not fall below a per‑address soulbound threshold. The check iterates over the ids array and compares balanceOf(address, id)‑value against soulboundKeyAmounts[address][id]. However, the loop treats each entry independently and does not enforce uniqueness of IDs. An attacker can craft a batch transfer where the same key ID appears multiple times with values that together exceed the user’s total balance but individually satisfy the check because each iteration sees the original balance minus a single value. Consequently, all of the user’s keys for that ID can be transferred despite the soulbound rule. The same duplication issue affects the internal _manageIndexes function, which removes an ID from the addressKeys and keyHolders mappings only when the transferred amount equals the full balance for that ID. When duplicate IDs are present, the balance check never matches the transferred amount, leaving stale entries in the index structures even after the user no longer holds any keys. This results in user‑facing symptoms such as a balance that drops to zero while the UI still lists the address as a holder of the key, or a user expecting a non‑transferable key to remain locked but seeing it moved to another address. The bug was discovered during a manual audit of the soulbound enforcement logic, where the reviewer noticed that the loop does not deduplicate IDs and that the index cleanup condition relies on a single equality test. The issue is subtle because the contract does not revert; the transfer appears successful, making it hard to detect without inspecting the internal state or testing edge cases with duplicate IDs. The impact is high: it breaks the core business rule that certain keys are non‑transferable, potentially allowing malicious actors with transfer permissions to move all keys from a victim, undermining trust in the protocol’s tokenomics and ownership guarantees. The vulnerability belongs to the class of “batch‑operation input validation” bugs where duplicate identifiers bypass per‑item checks, and to “state‑inconsistency” bugs where auxiliary data structures are not updated due to flawed equality conditions. To remediate, the contract should either reject duplicate IDs in batch operations or aggregate values per unique ID before performing the soulbound balance check and before invoking the index‑removal logic, ensuring that the total transferred amount for each ID is considered atomically. Additionally, the index‑maintenance code should be revised to handle cases where the total transferred amount equals the full balance, regardless of how many entries in the batch refer to the same ID.
