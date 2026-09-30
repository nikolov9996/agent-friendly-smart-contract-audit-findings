---
id: 23254
severity: "High"
---

# User can pay less protected listing fees when unlocking multiple listings

## Description

ProtectedListings.unlockProtectedListing() function create checkpoint after decrease listingCount[_collection]. Therefore, when user unlock multiple protected listings, user will pay less fees for the second and thereafter listings than the first listing.
ProtectedListings.unlockProtectedListing() function is following.
```solidity
function unlockProtectedListing(address _collection, uint _tokenId, bool _withdraw) public lockerNotPaused {
    // Ensure this is a protected listing
    ProtectedListing memory listing = _protectedListings[_collection][_tokenId];
    // Ensure the caller owns the listing
    if (listing.owner != msg.sender) revert CallerIsNotOwner(listing.owner);
    // Ensure that the protected listing has run out of collateral
    int collateral = getProtectedListingHealth(_collection, _tokenId);
    if (collateral < 0) revert InsufficientCollateral();
    // cache
    ICollectionToken collectionToken = locker.collectionToken(_collection);
    uint denomination = collectionToken.denomination();
    uint96 tokenTaken = _protectedListings[_collection][_tokenId].tokenTaken;
    // Repay the loaned amount, plus a fee from lock duration
    uint fee = unlockPrice(_collection, _tokenId) * 10 ** denomination;
    collectionToken.burnFrom(msg.sender, fee);
    // We need to burn the amount that was paid into the Listings contract
    collectionToken.burn((1 ether - tokenTaken) * 10 ** denomination);
    // Remove our listing type
    unchecked { --listingCount[_collection]; }
    // Delete the listing objects
    delete _protectedListings[_collection][_tokenId];
    // Transfer the listing ERC721 back to the user
    if (_withdraw) {
        locker.withdrawToken(_collection, _tokenId, msg.sender);
        emit ListingAssetWithdraw(_collection, _tokenId);
    } else {
        canWithdrawAsset[_collection][_tokenId] = msg.sender;
    }
    // Update our checkpoint to reflect that listings have been removed
    _createCheckpoint(_collection);
    // Emit an event
    emit ListingUnlocked(_collection, _tokenId, fee);
}
```
As can be seen, the above function decrease listingCount[_collection] in L311 before creating checkpoint in L325. However, creating checkpoint uses utilization rate and the utilization rate depends on listingCount[_collection]. Since listingCount[_collection] is already decreased at L311, the utilization rate is calculated incorrect and so the checkpoint will be incorrect.
PoC: Add the following test code into ProtectedListings.t.sol.
```solidity
function test_unlockProtectedListingError() public {
    erc721a.mint(address(this), 0);
    erc721a.mint(address(this), 1);
    erc721a.setApprovalForAll(address(protectedListings), true);
    uint[] memory _tokenIds = new uint[](2); _tokenIds[0] = 0; _tokenIds[1] = 1;
    // create protected listing for tokenId = 0 and tokenId = 1
    IProtectedListings.CreateListing[] memory _listings = new IProtectedListings.CreateListing[](1);
    _listings[0] = IProtectedListings.CreateListing({
        collection: address(erc721a),
        tokenIds: _tokenIds,
        listing: IProtectedListings.ProtectedListing({
            owner: payable(address(this)),
            tokenTaken: 0.4 ether,
            checkpoint: 0
        })
    });
    protectedListings.createListings(_listings);
    vm.warp(block.timestamp + 7 days);
    // unlock protected listing for tokenId = 0
    assertEq(protectedListings.unlockPrice(address(erc721a), 0), 402485479451875840);
    locker.collectionToken(address(erc721a)).approve(address(protectedListings), 402485479451875840);
    protectedListings.unlockProtectedListing(address(erc721a), 0, true);
    // unlock protected listing for tokenId = 0, but the unlock price for tokenId = 1 is 402055890410801920 < 402485479451875840 for tokenId = 0.
    assertEq(protectedListings.unlockPrice(address(erc721a), 1), 402055890410801920);
    locker.collectionToken(address(erc721a)).approve(address(protectedListings), 402055890410801920);
    protectedListings.unlockProtectedListing(address(erc721a), 1, true);
}
```
In the above test code, we can see that user paid less fees for tokenId = 1 than tokenId = 0.
Users will pay less fees. It means loss of funds for the protocol.

## Proof of Concept

no poc

## Recommendation

Change the order of decreasing listingCount[_collection] and creating checkpoint in ProtectedListings.unlockProtectedListing() function as follows.
```solidity
function unlockProtectedListing(address _collection, uint _tokenId, bool _withdraw) public lockerNotPaused {
    // Ensure this is a protected listing
    ProtectedListing memory listing = _protectedListings[_collection][_tokenId];
    // Ensure the caller owns the listing
    if (listing.owner != msg.sender) revert CallerIsNotOwner(listing.owner);
    // Ensure that the protected listing has run out of collateral
    int collateral = getProtectedListingHealth(_collection, _tokenId);
    if (collateral < 0) revert InsufficientCollateral();
    // cache
    ICollectionToken collectionToken = locker.collectionToken(_collection);
    uint denomination = collectionToken.denomination();
    uint96 tokenTaken = _protectedListings[_collection][_tokenId].tokenTaken;
    // Repay the loaned amount, plus a fee from lock duration
    uint fee = unlockPrice(_collection, _tokenId) * 10 ** denomination;
    collectionToken.burnFrom(msg.sender, fee);
    // We need to burn the amount that was paid into the Listings contract
    collectionToken.burn((1 ether - tokenTaken) * 10 ** denomination);
    // Remove our listing type
    // Delete the listing objects
    delete _protectedListings[_collection][_tokenId];
    // Transfer the listing ERC721 back to the user
    if (_withdraw) {
        locker.withdrawToken(_collection, _tokenId, msg.sender);
        emit ListingAssetWithdraw(_collection, _tokenId);
    } else {
        canWithdrawAsset[_collection][_tokenId] = msg.sender;
    }
    // Update our checkpoint to reflect that listings have been removed
    _createCheckpoint(_collection);
    unchecked { --listingCount[_collection]; }
    // Emit an event
    emit ListingUnlocked(_collection, _tokenId, fee);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an ordering flaw in the unlockProtectedListing function of the ProtectedListings contract. When a user unlocks a protected listing, the function first decrements the per‑collection listingCount and only afterwards creates a checkpoint that records the current utilization rate. The utilization rate, which is used by unlockPrice to compute the fee that must be burned, is derived from listingCount. Because the count has already been reduced, the checkpoint reflects a lower utilization than the actual state before the removal, causing unlockPrice to be calculated with a smaller fee. As a result, if a user unlocks several listings in the same collection within a single transaction or sequentially, the fee for the second and subsequent listings is lower than the fee for the first listing. An attacker can exploit this by creating multiple protected listings and then unlocking them one after another, paying less than the protocol expects and thereby extracting a profit equal to the difference between the correct fee and the under‑charged fee. The impact is a loss of revenue for the protocol, as the protocol’s accounting assumes that each unlock pays a fee proportional to the time the asset was locked and the utilization of the collection; the bug breaks this accounting assumption and effectively creates a fee‑dump where funds disappear from the protocol’s treasury. The condition occurs whenever the unlockProtectedListing function is called for a collection that has more than one active protected listing and the caller is the owner of those listings; the bug is triggered after the first listing is removed because the checkpoint is built on a stale, already‑decremented listingCount. Users of the protocol, especially lenders and token owners, are affected because they may see their expected fee higher than the amount actually deducted, and the protocol may suffer reduced fee income. The issue was discovered during a manual audit that examined the sequence of state updates and identified that the checkpoint creation relied on a variable that had been mutated earlier in the same function. The bug is subtle because the fee calculation still succeeds and the transaction does not revert; the only symptom is that the fee for later unlocks is unexpectedly lower, which may not be obvious without inspecting the checkpoint logic. The proper fix is to reorder the operations so that the checkpoint is created before the listingCount is decremented, or to compute the utilization rate using the pre‑decrement count, thereby ensuring that the fee calculation reflects the true state of the collection at the moment of unlocking. This class of vulnerability belongs to state‑inconsistency or ordering bugs where mutable state is used for accounting after it has been altered, leading to incorrect financial calculations.
