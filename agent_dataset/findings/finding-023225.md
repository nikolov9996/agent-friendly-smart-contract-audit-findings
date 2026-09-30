---
id: 23225
severity: "High"
---

# Lister is overpaying during the

## Description

Lister unfairly double pays the tax used while he is cancelling his listing through Listings::cancelListings().
When a user is creating his listing through Listings::createListings(), he is paying upfront the tax that is expected to be used for the whole duration of the listing.
However, if he decides to cancel the listing after some time calling Listings::cancelListings(), he will find himself paying again the portion of the tax that has been used until this point. Let's see the Listings::cancelListings():
```solidity
function cancelListings(address _collection, uint[] memory _tokenIds, bool _payTaxWithEscrow) public lockerNotPaused {
    uint fees;
    uint refund;
    for (uint i; i < _tokenIds.length; ++i) {
        uint _tokenId = _tokenIds[i];
        // Read the listing in a single read
        Listing memory listing = _listings[_collection][_tokenId];
        // Ensure the caller is the owner of the listing
        if (listing.owner != msg.sender) revert CallerIsNotOwner(listing.owner);
        // We cannot allow a dutch listing to be cancelled. This will also check that a liquid listing has not
        // expired, as it will instantly change to a dutch listing type.
        Enums.ListingType listingType = getListingType(listing);
        if (listingType != Enums.ListingType.LIQUID) revert CannotCancelListingType();
        // Find the amount of prepaid tax from current timestamp to prepaid timestamp
        // and refund unused gas to the user.
        (uint _fees, uint _refund) = _resolveListingTax(listing, _collection, false);
        emit ListingFeeCaptured(_collection, _tokenId, _fees);
        fees += _fees;
        refund += _refund;
        // Delete the listing objects
        delete _listings[_collection][_tokenId];
        // Transfer the listing ERC721 back to the user
        locker.withdrawToken(_collection, _tokenId, msg.sender);
    }
    // cache
    ICollectionToken collectionToken = locker.collectionToken(_collection);
    // Burn the ERC20 token that would have been given to the user when it was initially created
    uint requiredAmount = ((1 ether * _tokenIds.length) * 10 ** collectionToken.denomination()) - refund;
    payTaxWithEscrow(address(collectionToken), requiredAmount, _payTaxWithEscrow);
    collectionToken.burn(requiredAmount + refund);
}
```
Link to code
As we can see, user is expected to return back the whole 1e18-refund. It helps to remember that when he created the listing he “took” 1e18-TAX where, now, TAX=refund+fees. So the user is expected to give back to the protocol 1e18-refund while he got 1e18-refund-fees. The difference of what he got at the start and what he is expected to return now:
whatHeGot - whatHeMustReturn = (1e18 - refund - fees) - (1e18 - refund) = -fees
So, now the user has to get out of his pocket and pay again for the fees while, technically, he has paid for them in the start by not ever taking them.
Furthermore, in this way, as we can see from this line, the protocol burns the whole 1e18 without considering the tax that got actually used and shouldn't be burned as it will be deposited to the UniswapV4Implementation:
```solidity
collectionToken.burn(requiredAmount + refund);
```
Internal pre-conditions
1. User creates a listing from Listings::createListings().
External pre-conditions
1. User wants to cancel his listing by Listings::cancelListings().
Attack Path
1. User creates a listing from Listings::createListings() and takes back as collectionTokens -> 1e18-prepaidTax.
2. Some time passes by.
3. User wants to cancel the listing by calling Listings::cancelListings() and he has to give back 1e18-unusedTax. This mean that he has to give also the usedTax amount.
The impact of this serious vulnerability is that the user is forced to double pay the tax that has been used for the duration that his listing was up. He, firstly, paid for it by not taking it and now, when he cancels the listing, he has to pay it again out of his own pocket. This results to unfair loss of funds for whoever tries to cancel his listing.

## Proof of Concept

No PoC needed.

## Recommendation

To mitigate this vulnerability successfully, consider not requiring user to return the fee variable as well:
```solidity
function cancelListings(address _collection, uint[] memory _tokenIds, bool _payTaxWithEscrow) public lockerNotPaused {
    uint fees;
    uint refund;
    for (uint i; i < _tokenIds.length; ++i) {
    }
    // cache
    ICollectionToken collectionToken = locker.collectionToken(_collection);
    // Burn the ERC20 token that would have been given to the user when it was initially created
    uint requiredAmount = ((1 ether * _tokenIds.length) * 10 ** collectionToken.denomination()) - refund - fees;
    payTaxWithEscrow(address(collectionToken), requiredAmount, _payTaxWithEscrow);
    collectionToken.burn(requiredAmount + refund);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error in the cancellation flow of a marketplace listing that causes the listing owner to pay the tax for the used portion of the listing twice. When a user creates a listing they pre‑pay a fixed tax amount that is intended to cover the entire lifetime of the listing. The contract records this prepaid tax as a token balance (typically 1 ether per listed token). If the owner later cancels the listing before it expires, the cancel function calculates two values: the fees that correspond to the tax already consumed (used tax) and the refund that corresponds to the unused tax. The code then asks the caller to return the full prepaid amount minus the refund, but it adds the previously collected fees back into the amount that must be paid again. As a result the user must pay the used tax a second time out of pocket, even though it was already deducted when the listing was created. In addition, the function burns the entire prepaid token amount (requiredAmount + refund) without subtracting the used tax, effectively destroying tokens that should have been retained for the protocol’s tax pool. The root cause is a mis‑calculation of the requiredAmount variable and an incorrect burn call that does not account for fees already paid. The bug is triggered whenever a listing of type LIQUID is cancelled before its expiration, which is a normal user action. The impact is a direct financial loss for any user who cancels a listing: they receive a refund for the unused portion but are also forced to pay again for the tax that was already consumed, leading to double payment and a reduction of their balance. From the user’s perspective the UI may show a normal refund amount, yet the final balance after the transaction is lower than expected, sometimes appearing as if the funds “disappear” or the refund is missing. The issue was discovered during a manual audit of the contract’s cancelListings function, where the auditor noticed that the fee variable was added to the amount the user must return and that the burn operation ignored the already‑paid fees. Because the function emits a fee capture event and then immediately burns tokens, the overpayment can be subtle and may not raise an immediate alarm, especially if the user does not compare the prepaid tax with the final amount transferred. To remediate the problem the requiredAmount calculation should subtract both the refund and the fees, or the contract should simply not require the caller to return the fee portion at all. The burn call must also be adjusted to only destroy the unused tax, preserving the tokens that represent the consumed tax for the protocol’s accounting. This correction restores the intended economic model where users only lose the tax that corresponds to the time their listing was active and receive a proper refund for the remaining period.
