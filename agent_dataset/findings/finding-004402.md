---
id: 4402
severity: "High"
---

# clear() only deletes ﬁrst element from linked list

## Description

The linked list clear() functions have the following deﬁnition (using the AddressLinkedList as an example):
```solidity
function clear(mapping(address => address) storage self) internal {
    for (
        address cursor = self[SENTINEL_ADDRESS];
        uint160(cursor) > SENTINEL_UINT;
        cursor = self[cursor]
    ) {
        delete self[cursor];
    }
    delete self[SENTINEL_ADDRESS];
}
```
In this code, notice that the delete self[cursor] statement will happen immediately before the cursor = self[cursor] advancement in the for loop. Since self[cursor] is being deleted before advancing, the loop will always exit after the ﬁrst iteration, and the list won't be cleared as expected. As a consequence, the resetOwners() function (used by recovery modules) will not correctly clear the previous owners.

## Proof of Concept

no poc

## Recommendation

To properly delete all elements, use a temporary nextCursor value as follows:
```solidity
function clear(mapping(address => address) storage self) internal {
    address nextCursor;
    for (
        address cursor = self[SENTINEL_ADDRESS];
        uint160(cursor) > SENTINEL_UINT;
        cursor = nextCursor
    ) {
        nextCursor = self[cursor];
        delete self[cursor];
    }
    delete self[SENTINEL_ADDRESS];
}
```
Alternatively, consider using a do-while loop in a similar way:
```solidity
function clear(mapping(address => address) storage self) internal {
    address cursor = SENTINEL_ADDRESS;
    do {
        address nextCursor = self[cursor];
        delete self[cursor];
        cursor = nextCursor;
    } while (uint160(cursor) > SENTINEL_UINT);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incomplete clearing routine in a singly linked list implementation used by the contract's recovery module. The 'clear()' function iterates over the list starting from the sentinel node, deletes the current node, and then moves the cursor to self[cursor]. Because the deletion occurs before the cursor is advanced, the mapping entry that stores the next pointer is removed, so the subsequent iteration reads a zero address and the loop terminates after the first element. As a result only the first element of the list is removed while the rest remain in storage. This bug originates from the order of operations in the for‑loop and the fact that Solidity's delete clears the mapping entry, erasing the link to the next node. An attacker or a malicious recovery module can trigger resetOwners(), which relies on 'clear()' to wipe the list of previous owners before assigning new ones. Since the list is not fully cleared, stale owner addresses stay registered, allowing them to retain privileges or to block legitimate recovery attempts. The impact is that the protocol may retain outdated ownership data, leading to unauthorized access, denial of service for rightful owners, or incorrect accounting of ownership rights. The condition occurs whenever resetOwners() is called, typically during a recovery flow after a security incident. All participants that depend on the recovery module – users, guardians, and the protocol itself – are affected because the contract state no longer reflects the intended ownership set. The issue was discovered during a manual audit of the linked‑list utilities, where the loop logic was examined and it was observed that the cursor variable is overwritten after the delete, causing early termination. The bug can be subtle because the function does not revert and appears to run without error; only the persistent storage after execution reveals that most entries are still present. The proper fix is to store the next pointer in a temporary variable before deleting the current node, or to restructure the loop as a do‑while that updates the cursor after the deletion. This ensures every node is visited and removed, guaranteeing that resetOwners() truly empties the list and that no residual owners remain. In user‑facing terms, a user attempting to recover a wallet may see that their previous owners are still listed, or that the contract reports ownership still belonging to old addresses, contrary to the expectation that the recovery clears all owners.
