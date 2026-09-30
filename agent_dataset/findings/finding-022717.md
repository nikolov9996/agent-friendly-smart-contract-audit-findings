---
id: 22717
severity: "High"
---

# Original collection referrer will be overwritten

## Description

Original collection referrers will be overwritten when a new collection/work is created. This results in the original collection referrers being unable to collect the fee they are entitled to, leading to a loss of assets for them.
Contest's Discord Channel.
There are two types of referrers in this ecosystem. The first is a collection referrer, who refers the creation of a new Edition, and gets a cut of all mint fees for that Edition. The second is a mint referrer, who refers a mint and gets a cut of the mint fee for that mint.
The following describes the difference between collection referrer and mint referrer.
• User 1 creates a referral link to create a collection
• User 2 uses that link to publish a collection
• User 3 mints that collection. For this mint, user1 is treated as the collection referrer
• User 4 creates a referral link to mint that collection
• User 5 mints that collection. For this mint, user1 is treated as the collection referrer and user4 is treated as the mint referrer
Assume that Alice creates a referral link to create a collection. Bob uses that link to publish a new collection/work called CollectionA that is based on an Edition called EditionA. The collection referrer of CollectionA will Alice.
Bob will call the following TitlesCore.publish function with the edition parameter set to EditionA and the referrer_ parameter will be automatically set to Alice by the front end.
```solidity
/// @notice Publishes a new Work in the given {Edition} using the given payload.
/// @param edition_ The {Edition} to publish the Work in.
/// @param payload_ The compressed payload for publishing the Work. See {WorkPayload}.
/// @param referrer_ The address of the referrer.
/// @return tokenId The token ID of the new Work.
function publish(Edition edition_, bytes calldata payload_, address referrer_)
    external
    nonReentrant
    returns (uint256 tokenId)
{
    // Ensure this Edition is authorized
    if (!edition_.isAuthorized()) revert Unauthorized();
    // Decode the payload to get the work attributes
    Work memory work_ = _decodePayload(payload_);
    // Validate the work
    _validateWork(work_, payload_);
    // Store the work
    tokenId = _mint(edition_, msg.sender, 1, "");
    works[tokenId] = work_;
    WorkPublished(edition_, tokenId, work_, payload_);
    // Wake-Disable-next-line reentrancy
    // Create the fee route for the new Work
    // wake-disable-next-line reentrancy
    Target memory feeReceiver = feeManager.createRoute(
        edition_, tokenId, _attributionTargets(work_.attributions), referrer_
    );
}
```
Within the TitlesCore.publish, the following feeManager.createRoute function will be executed internally. The feeManager.createRoute function will store Alice's wallet address within the referrers[edition_] mapping. Thus, the state of the referrers mapping will be as follows:
referrers[Edition_A] = Alice
```solidity
function createRoute(
    IEdition edition_,
    uint256 tokenId_,
    Target[] calldata attributions_,
    address referrer_
) external onlyOwnerOrRoles(ADMIN_ROLE) returns (Target memory receiver) {
    // Prevent duplicate routes
    bytes32 routeId = getRouteId(edition_, tokenId_);
    if (_feeReceivers[routeId].rate != 0) revert InvalidCall();
    // Calculate total attribution basis points
    uint256 totalBps;
    // The Edition and the creator always earn, as long as the Edition's strategy allows attribution
    targetList.push(edition_._getTarget());
    rateList.push(edition_.strategy().defaultCreatorBps);
    totalBps += edition_.strategy().defaultCreatorBps;
    targetList.push(work_.creator.target);
    rateList.push(work_.creator.rateBps);
    totalBps += work_.creator.rateBps;

    _feeReceivers[getRouteId(edition_, tokenId_)] = receiver;
    referrers[edition_] = referrer_;
}
```
When someone mints a new token for CollectionA, Alice, who is the collection referrer, will get a share of the minting fee per Line 421 below.
```solidity
function _splitProtocolFee(
    IEdition edition_,
    address asset_,
    uint256 amount_,
    address payer_,
    address referrer_
) internal returns (uint256 referrerShare) {
    // The creation and mint referrers earn 25% and 50% of the protocol's share respectively, if applicable
    uint256 mintReferrerShare = getMintReferrerShare(amount_, referrer_);
    uint256 collectionReferrerShare = getCollectionReferrerShare(amount_, referrers[edition_]);
    referrerShare = mintReferrerShare + collectionReferrerShare;
}
```
Let's assume Charles also creates a referral link to create a collection. David uses that link to publish a new collection/work called CollectionB that is based on the same Edition called EditionA. The collection referral of CollectionB will be Charles.
When the FeeManager.createRoute function is executed during the publishing of the new work/collection, Charles's wallet address will be stored within the referrers[edition_] mapping. Thus, the state of the referrers mapping will be as follows:
referrers[Edition_A] = Charles
```solidity
function createRoute(
    IEdition edition_,
    uint256 tokenId_,
    Target[] calldata attributions_,
    address referrer_
) external onlyOwnerOrRoles(ADMIN_ROLE) returns (Target memory receiver) {
    // Prevent duplicate routes
    bytes32 routeId = getRouteId(edition_, tokenId_);
    if (_feeReceivers[routeId].rate != 0) revert InvalidCall();
    // Calculate total attribution basis points
    uint256 totalBps;
    // The Edition and the creator always earn, as long as the Edition's strategy allows attribution
    targetList.push(edition_._getTarget());
    rateList.push(edition_.strategy().defaultCreatorBps);
    totalBps += edition_.strategy().defaultCreatorBps;
    targetList.push(work_.creator.target);
    rateList.push(work_.creator.rateBps);
    totalBps += work_.creator.rateBps;

    _feeReceivers[getRouteId(edition_, tokenId_)] = receiver;
    referrers[edition_] = referrer_;
}
```
to Charles here. At this point onwards, if someone mints tokens for CollectionA, the collection referral fee will be routed to Charles instead of Alice. Alice is the referral for CollectionA, yet she does not receive the referral fee, resulting in a loss of assets for Alice.
Loss of assets as shown in the above scenario. The original collection referrers are unable to collect the fee they are entitled to, leading to a loss of assets for them.

## Proof of Concept

no poc

## Recommendation

Consider the following changes to ensure that the collection referral fee is routed to the correct collection referrer for each collection/work.
With the following changes, Alice will continue to receive the collection referral fee for CollectionA and Bob will receive the collection referral fee for CollectionB even if there are multiple collections/works for a specific Edition.
```solidity
function createRoute(
    IEdition edition_,
    uint256 tokenId_,
    Target[] calldata attributions_,
    address referrer_
) external onlyOwnerOrRoles(ADMIN_ROLE) returns (Target memory receiver) {
    // Prevent duplicate routes
    bytes32 routeId = getRouteId(edition_, tokenId_);
    if (_feeReceivers[routeId].rate != 0) revert InvalidCall();
    // Calculate total attribution basis points
    uint256 totalBps;
    // The Edition and the creator always earn, as long as the Edition's strategy allows attribution
    targetList.push(edition_._getTarget());
    rateList.push(edition_.strategy().defaultCreatorBps);
    totalBps += edition_.strategy().defaultCreatorBps;
    targetList.push(work_.creator.target);
    rateList.push(work_.creator.rateBps);
    totalBps += work_.creator.rateBps;

    _feeReceivers[getRouteId(edition_, tokenId_)] = receiver;
    referrers[getRouteId(edition_, tokenId_)] = referrer_;
}
```
```solidity
function _splitProtocolFee(
    IEdition edition_,
    uint256 tokenId,
    address asset_,
    uint256 amount_,
    address payer_,
    address referrer_
) internal returns (uint256 referrerShare) {
    // The creation and mint referrers earn 25% and 50% of the protocol's share respectively, if applicable
    uint256 mintReferrerShare = getMintReferrerShare(amount_, referrer_);
    uint256 collectionReferrerShare = getCollectionReferrerShare(amount_, referrers[getRouteId(edition_, tokenId)]);
    referrerShare = mintReferrerShare + collectionReferrerShare;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect storage of the collection referrer in the fee manager. When a new collection (or work) is published, the contract creates a fee route and stores the address of the collection referrer in a mapping called referrers that is indexed only by the Edition contract address. Because the key does not include the tokenId of the newly created collection, publishing a second collection that uses the same Edition overwrites the previous entry. As a result, the original collection referrer is no longer associated with the first collection and the splitProtocolFee routine reads the overwritten address, sending the collection‑referral share of every mint to the most recent referrer. The bug occurs whenever multiple collections are created under the same Edition, which is a common pattern in the Titles publishing protocol. The impact is that the first referrer loses the portion of the mint fee they are entitled to; from a user perspective the expected referral reward is zero, balances appear unchanged and the protocol’s accounting for referral fees becomes inaccurate. The issue was discovered during a manual audit of the publish and fee‑distribution logic, where the mapping key was identified as too coarse. It is hard to notice because the fee distribution for the newly created collection works correctly, while the older collection silently stops receiving its share. The proper fix is to index the referrer mapping by the unique route identifier (edition address together with tokenId) and to read that entry when calculating the collection‑referrer share, ensuring each collection retains its own referrer. This class of bug belongs to the category of state‑key collision or improper scoping of per‑instance data, leading to fee‑routing errors and loss of assets.
