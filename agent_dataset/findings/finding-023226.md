---
id: 23226
severity: "High"
---

# Incorrect index handling in checkpoint creation leads to incorrect initial checkpoint retrieval and potential DoS Found by 0x37, ComposableSecurity, Ironsidesec, KungFuPanda, McToady, Ollam, Tendency, blockchain555, dany.armstrong90, g, h2134, heeze, merlinboii, stuart_the_minion, zzykxx

## Description

In the current implementation of , when multiple listings are created for the same collection at the same timestamp, the existing checkpoint is updated, and no new checkpoint is pushed. However, the function incorrectly returns the wrong index for this case leads to incorrect index referencing during subsequent listing creations. When a checkpoint is created at the same timestamp, the existing checkpoint is updated, and no new checkpoint is pushed.
```solidity
function _createCheckpoint(address _collection) internal returns (uint index_) {
    // Determine the index that will be created
    index_ = collectionCheckpoints[_collection].length;
    // Get our new (current) checkpoint
    Checkpoint memory checkpoint = _currentCheckpoint(_collection);

    // If no time has passed in our new checkpoint, then we just need to update the
    // utilization rate of the existing checkpoint.
    if (checkpoint.timestamp == collectionCheckpoints[_collection][index_ - 1].timestamp) {
        collectionCheckpoints[_collection][index_ - 1].compoundedFactor = checkpoint.compoundedFactor;
        return index_;
    }
}
```
However, the current implementation returns the wrong index for this case, causing incorrect checkpoint handling for new listing creations, especially when creating multiple listings for the same collection with different variations.
```solidity
function createListings(CreateListing[] calldata _createListings) public nonReentrant lockerNotPaused {
    checkpointKey = keccak256(abi.encodePacked('checkpointIndex', listing.collection));
    assembly { checkpointIndex := tload(checkpointKey) }
    if (checkpointIndex == 0) {
        checkpointIndex = _createCheckpoint(listing.collection);
        assembly { tstore(checkpointKey, checkpointIndex) }
    }
    tokensReceived = _mapListings(listing, tokensIdsLength, checkpointIndex) * 10 ** locker.collectionToken(listing.collection).denomination();
}
```
An edge case arises when a new listing is created for a collection that has no checkpoints (collectionCheckpoints[_collection].length==0). Assuming erc721b has no existing checkpoints (length = 0):
• Creating 2 CreateListings for the same collection (erc721b) with different variants should result in only one checkpoint being created.
• In the first iteration, the returns 0 as the index, stores it in checkpointIndex, and updates the transient storage at the checkpointKey slot. The listing is then stored with the current checkpoint.
```solidity
function createListings(CreateListing[] calldata _createListings) public nonReentrant lockerNotPaused {
    checkpointKey = keccak256(abi.encodePacked('checkpointIndex', listing.collection));
    assembly { checkpointIndex := tload(checkpointKey) }
    if (checkpointIndex == 0) {
        checkpointIndex = _createCheckpoint(listing.collection);
        assembly { tstore(checkpointKey, checkpointIndex) }
    }
    tokensReceived = _mapListings(listing, tokensIdsLength, checkpointIndex) * 10 ** locker.collectionToken(listing.collection).denomination();
}
```
• In the second iteration, since checkpointKey stores 0, is triggered again and returns 1 (the length of checkpoints) even though no new checkpoint was pushed. As a result, the second iteration incorrectly references index 1, even though the checkpoint only exists at index 0 (with a length of 1). This causes incorrect indexing for the listings. Incorrect index returns lead to the wrong initial checkpoint index for new listings, causing incorrect checkpoint retrieval and utilization. This can result in inaccurate data and potential out-of-bound array access, leading to a Denial of Service (DoS) in

## Proof of Concept

no poc

## Recommendation

Update the return value of the ProtectedListings::_createCheckpoint() to return index_-1 when the checkpoint is updated at the same timestamp to ensure that subsequent listings reference the correct index.
```solidity
function _createCheckpoint(address _collection) internal returns (uint index_) {
    // Determine the index that will be created
    index_ = collectionCheckpoints[_collection].length;
    // Get our new (current) checkpoint
    Checkpoint memory checkpoint = _currentCheckpoint(_collection);

    // If no time has passed in our new checkpoint, then we just need to update the
    // utilization rate of the existing checkpoint.
    if (checkpoint.timestamp == collectionCheckpoints[_collection][index_ - 1].timestamp) {
        collectionCheckpoints[_collection][index_ - 1].compoundedFactor = checkpoint.compoundedFactor;
        return (index_ - 1);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The issue is an incorrect handling of checkpoint indices during the creation of listings for a collection. When the contract creates a checkpoint, it determines the index to be the current length of the collection's checkpoint array. If a new listing is added at the same block timestamp as an existing checkpoint, the code updates the existing checkpoint instead of pushing a new one, but it still returns the length of the array as the index. Consequently, the calling function stores this wrong index in transient storage and later uses it to reference a checkpoint that does not exist. This edge case appears when a collection starts with zero checkpoints and multiple listings are created in the same transaction or block, each with the same timestamp. The root cause is the return statement in the internal _createCheckpoint function, which returns index_ (the array length) even when the checkpoint is merely updated; the correct value should be index_-1. An attacker or even a normal user can trigger the bug by submitting two listings for the same collection at the same timestamp, causing the second listing to reference a non‑existent checkpoint. This can lead to out‑of‑bounds array access, causing the transaction to revert or the contract to become stuck, effectively a denial‑of‑service condition. From a user perspective, listings may appear to be created but later show zero utilization, missing data, or the transaction may fail silently, leading to confusion and potential loss of expected functionality. The protocol’s accounting logic is violated because utilization rates are read from the wrong checkpoint, breaking the invariant that each listing corresponds to a valid checkpoint. The vulnerability was discovered during a manual audit by the Sherlock team, and it is subtle because the logic works correctly for the common case where timestamps differ; only the specific scenario of identical timestamps with an initially empty checkpoint array triggers the faulty index. Fixing the issue requires adjusting the return value of _createCheckpoint to return index_-1 when the checkpoint is updated, ensuring that subsequent listings reference the correct existing checkpoint and preventing out‑of‑bounds reads and the associated denial‑of‑service risk.
