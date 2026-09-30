---
id: 22645
severity: "High"
---

# Auction creators have the ability to lock bid-

## Description

Auction creators have the ability to cancel an auction before it starts. However, once the auction begins, they should not be allowed to cancel it. During the auction, bidders can place bids and send quote tokens to the auction house. After the auction concludes, bidders can either receive base tokens or retrieve their quote tokens. Unfortunately, batch auction creators can cancel an auction when it ends. This means that auction creators can cancel their auctions if they anticipate losses. This should not be allowed. The significant risk is that bidders' funds could become locked in the auction house.
Auction creators can not cancel an auction once it concludes.
```solidity
function cancelAuction(uint96 lotId_) external override onlyInternal {
    _revertIfLotConcluded(lotId_);
}
```
They also can not cancel it while it is active.
```solidity
function _cancelAuction(uint96 lotId_) internal override {
    _revertIfLotActive(lotId_);
    auctionData[lotId_].status = Auction.Status.Claimed;
}
```
When the block.timestamp aligns with the conclusion time of the auction, we can bypass these checks.
```solidity
function _revertIfLotConcluded(uint96 lotId_) internal view virtual {
    if (lotData[lotId_].conclusion < uint48(block.timestamp)) {
        revert Auction_MarketNotActive(lotId_);
    }
    if (lotData[lotId_].capacity == 0) revert Auction_MarketNotActive(lotId_);
}

function _revertIfLotActive(uint96 lotId_) internal view override {
    if (
        auctionData[lotId_].status == Auction.Status.Created
        && lotData[lotId_].start <= block.timestamp
        && lotData[lotId_].conclusion > block.timestamp
    ) revert Auction_WrongState(lotId_);
}
```
So Auction creators can cancel an auction when it concludes. Then the capacity becomes 0 and the auction status transitions to Claimed.
Bidders can not refund their bids.
```solidity
function refundBid(
    uint96 lotId_,
    uint64 bidId_,
    address caller_
) external override onlyInternal returns (uint96 refund) {
    _revertIfLotConcluded(lotId_);
}

function _revertIfLotConcluded(uint96 lotId_) internal view virtual {
    if (lotData[lotId_].capacity == 0) revert Auction_MarketNotActive(lotId_);
}
```
The only way for bidders to reclaim their tokens is by calling the claimBids function. However, bidders can only claim bids when the auction status is Settled.
```solidity
function claimBids(
    uint96 lotId_,
    uint64[] calldata bidIds_
) {
    _revertIfLotNotSettled(lotId_);
}
```
To settle the auction, the auction status should be Decrypted. This requires submitting the private key. The auction creator can not submit the private key or submit it without decrypting any bids by calling submitPrivateKey(lotId, privateKey, 0). Then nobody can decrypt the bids using the decryptAndSortBids function which always reverts.
```solidity
function decryptAndSortBids(uint96 lotId_, uint64 num_) external {
    if (
        auctionData[lotId_].status != Auction.Status.Created
        || auctionData[lotId_].privateKey == 0
    ) {
        revert Auction_WrongState(lotId_);
    }
    _decryptAndSortBids(lotId_, num_);
}
```
As a result, the auction status remains unchanged, preventing it from transitioning to Settled. This leaves the bidders' quote tokens locked in the auction house.
Please add below test to the test/modules/Auction/cancel.t.sol.
```solidity
function test_cancel() external whenLotIsCreated {
    Auction.Lot memory lot = _mockAuctionModule.getLot(_lotId);
    console2.log("lot.conclusion before ==> ", lot.conclusion);
    console2.log("block.timestamp before ==> ", block.timestamp);
    console2.log("isLive ==> ", _mockAuctionModule.isLive(_lotId));

    vm.warp(lot.conclusion - block.timestamp + 1);
    console2.log("lot.conclusion after ==> ", lot.conclusion);
    console2.log("block.timestamp after ==> ", block.timestamp);
    console2.log("isLive ==> ", _mockAuctionModule.isLive(_lotId));

    vm.prank(address(_auctionHouse));
    _mockAuctionModule.cancelAuction(_lotId);
}
```
The log is
lot.conclusion before ==> 86401
block.timestamp before ==> 0
isLive ==> true
lot.conclusion after ==> 86401
block.timestamp after ==> 86401
isLive ==> false
Users' funds can be locked.

## Proof of Concept

no poc

## Recommendation

```solidity
function _revertIfLotConcluded(uint96 lotId_) internal view virtual {
    if (lotData[lotId_].conclusion <= uint48(block.timestamp)) {
        revert Auction_MarketNotActive(lotId_);
    }
    // Capacity is sold-out, or cancelled
    if (lotData[lotId_].capacity == 0) revert Auction_MarketNotActive(lotId_);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a state‑transition flaw in the batch auction contract that allows the auction creator to cancel an auction after the scheduled conclusion time, effectively locking bidders’ quote tokens inside the auction house. The root cause is an off‑by‑one error in the _revertIfLotConcluded check, which only reverts when the current block timestamp is strictly less than the conclusion timestamp. When block.timestamp becomes equal to the conclusion, the check passes, allowing cancelAuction to be called. The cancel function then sets the auction capacity to zero and marks the status as Claimed, bypassing the intended restriction that cancellations are only permitted before the auction starts. Because the auction never reaches the Decrypted or Settled states, the subsequent refundBid and claimBids functions remain blocked – they each call _revertIfLotConcluded or _revertIfLotNotSettled, both of which now revert due to the zero capacity or unchanged status. As a result, bidders cannot retrieve their deposited quote tokens, and the tokens remain permanently locked in the contract. This condition occurs precisely at the moment the auction’s conclusion timestamp is reached, and it can be triggered by any creator with the internal cancelAuction permission. Users who placed bids see their balances unchanged after the auction ends, receive no refund, and may notice that the auction is no longer live despite having participated. The issue was discovered during a manual audit that examined the lifecycle checks for auction cancellation and bid settlement, and it is subtle because the contract’s public interface appears to prevent cancellation after start, yet the timing edge case is not obvious from a surface‑level review. The bug belongs to the class of improper state validation or time‑based access control errors, where boundary conditions are incorrectly handled, leading to a violation of the business rule that funds must be recoverable after an auction finishes. To remediate, the _revertIfLotConcluded function should reject calls when block.timestamp is greater than or equal to the conclusion timestamp, and the cancel logic should enforce that capacity is non‑zero and status is not already Claimed. Additionally, the auction settlement flow should ensure that a private key cannot be submitted without triggering decryption, preventing the creator from stalling the transition to Settled. Properly fixing these checks restores the guarantee that bidders can always claim or refund their tokens once the auction ends, aligning the contract’s behavior with expected auction economics.
