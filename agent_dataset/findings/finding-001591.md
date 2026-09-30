---
id: 1591
severity: "High"
---

# An offer made after auction end can be stolen by an auction winner

## Description

```solidity
An Offer which is made for an NFT when auction has ended, but its winner hasn’t received the NFT yet, can be stolen by this winner as `_transferFromEscrow` being called by `_acceptOffer` will transfer the NFT to the winner, finalising the auction, while no transfer to the user who made the offer will happen.

This way the auction winner will obtain both the NFT and the offer amount after the fees at no additional cost, at the expense of the user who made the offer.
```

## Proof of Concept

When an auction has ended, there is a possibility to make the offers for an auctioned NFT as:

`makeOffer` checks `_isInActiveAuction`:

`_isInActiveAuction` returns false when `auctionIdToAuction[auctionId].endTime < block.timestamp`, so `makeOffer` above can proceed:

Then, the auction winner can call `acceptOffer -> _acceptOffer` (or `setBuyPrice -> _autoAcceptOffer -> _acceptOffer`).

`_acceptOffer` will try to transfer directly, and then calls `_transferFromEscrow`:

If the auction has ended, but a winner hasn’t picked up the NFT yet, the direct transfer will fail, proceeding with `_transferFromEscrow` in the FNDNFTMarket defined order:
```solidity
    function _transferFromEscrow(
    address nftContract,
    uint256 tokenId,
    address recipient,
    address seller
    ) internal override(NFTMarketCore, NFTMarketReserveAuction, NFTMarketBuyPrice, NFTMarketOffer) {
    super._transferFromEscrow(nftContract, tokenId, recipient, seller);
    }
```
NFTMarketOffer._transferFromEscrow will call super as `nftContractToIdToOffer` was already deleted:

NFTMarketBuyPrice._transferFromEscrow will call super as there is no buy price set:

Finally, NFTMarketReserveAuction._transferFromEscrow will send the NFT to the winner via `_finalizeReserveAuction`, not to the user who made the offer:

The `recipient` user who made the offer is not present in this logic, the NFT is being transferred to the `auction.bidder`, and the original `acceptOffer` will go through successfully.

## Recommendation

```solidity
An attempt to set a buy price from auction winner will lead to auction finalisation, so `_buy` cannot be called with a not yet finalised auction, this way the NFTMarketReserveAuction._transferFromEscrow L550-L560 logic is called from the NFTMarketOffer._acceptOffer only:

is the only user of

This way the fix is to update L556-L560 for the described case as:

Now:
    
    // Finalization will revert if the auction has not yet ended.
    _finalizeReserveAuction(auctionId, false);
    
    // Finalize includes the transfer, so we are done here.
    return;

To be, we leave the NFT in the escrow and let L564 super call to transfer it to the recipient:
    
    // Finalization will revert if the auction has not yet ended.
    _finalizeReserveAuction(auctionId, true);
```
Yes! This was a great find and a major issue with our implementation. I’m very happy that it was flagged by a few different people, it helps raise our confidence that several wardens really dove into the code.

It was a big miss on our part that this was not thoroughly tested. Our tests for this scenario confirmed the events and payouts, but did not validate the ownership in the end!

The proposed fix is perfect and exactly what we have implemented. This follows the patterns we established well, and actually simplifies the logic here so that things are easier to reason about.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical flaw in the auction‑offer interaction that allows the auction winner to steal an offer that is submitted after the auction has officially ended but before the winner has claimed the NFT. The contract mistakenly treats an accepted offer as a trigger to finalize the reserve auction and calls the escrow‑transfer routine from the offer module. Because the auction is still in a non‑finalised state, the escrow routine forwards the NFT to the winning bidder instead of to the user who submitted the offer. Consequently the winner receives both the NFT (which they already own) and the offer amount after fees, while the offer maker receives neither the NFT nor a refund, effectively losing the funds they offered. This scenario occurs whenever the block timestamp exceeds the auction end time, the winner has not yet executed the claim function, and the contract’s `makeOffer` function still permits new offers because it checks only whether the auction is "active" in a way that returns false after the end time, unintentionally allowing offers to be created post‑auction. An attacker (the winner) can then invoke `acceptOffer` (or `setBuyPrice` that auto‑accepts) to trigger the flawed `_transferFromEscrow` path, which finalises the auction and transfers the NFT to the bidder, bypassing any transfer to the offer sender. The impact is a direct financial loss for the offer maker and a breach of the protocol’s accounting assumptions that an accepted offer should result in the transfer of the NFT to the offer sender. The issue was discovered during a Code4rena audit, where the auditors traced the call stack across multiple inherited contracts and noticed that the final ownership check was missing in the test suite, which only verified events and payouts. The problem is subtle because the contract’s state changes are spread across several modules, and the tests did not validate the final NFT holder, allowing the bug to remain hidden. To remediate, the contract should reject new offers once the auction end time has passed, or ensure that any acceptance of an offer after the auction’s end forces a proper finalisation that transfers the NFT to the offer initiator rather than the original winner. Alternatively, the escrow‑transfer logic should be guarded to prevent the reserve‑auction finalisation path from being invoked when handling offers after the auction has ended. Implementing these checks restores the intended business logic that an offer results in a single transfer of ownership and payment, preventing funds from disappearing unexpectedly.
