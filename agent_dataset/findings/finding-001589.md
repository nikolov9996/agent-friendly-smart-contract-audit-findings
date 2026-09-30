---
id: 1589
severity: "High"
---

# NFT owner can create multiple auctions

## Description

```solidity
[NFTMarketReserveAuction.sol#L325-L349](https://github.com/code-423n4/2022-02-foundation/blob/4d8c8931baffae31c7506872bf1100e1598f2754/contracts/mixins/NFTMarketReserveAuction.sol#L325-L349)  
[NFTMarketReserveAuction.sol#L596-L599](https://github.com/code-423n4/2022-02-foundation/blob/4d8c8931baffae31c7506872bf1100e1598f2754/contracts/mixins/NFTMarketReserveAuction.sol#L596-L599)  

NFT owner can permanently lock funds of bidders.
```

## Proof of Concept

Alice (the attacker) calls `createReserveAuction`, and creates one like normal. let this be auction id 1.

Alice calls `createReserveAuction` again, before any user has placed a bid (this is easy to guarantee with a deployed attacker contract). We’d expect that Alice wouldn’t be able to create another auction, but she can, because `_transferToEscrow` doesn’t revert if there’s an existing auction. let this be Auction id 2.

Since `nftContractToTokenIdToAuctionId[nftContract][tokenId]` will contain auction id 2, all bidders will see that auction as the one to bid on (unless they inspect contract events or data manually).

Alice can now cancel auction id 1, then cancel auction id 2, locking up the funds of the last bidder on auction id 2 forever.

## Recommendation

```solidity
Prevent NFT owners from creating multiple auctions.
```
This is a great find!

The impact of this bug is:

  * Bidder’s funds are stuck in escrow in an unrecoverable way without an upgrade, and even with an upgrade it would have been non-trivial to offer a migration path to recover the funds (but it would have been possible to recover correctly).
  * It allows sellers to stop the clock and/or back out of an auction. Normally once a bid is received we do not allow the seller to cancel the auction. With this bug, they could have created a new auction and then cancel that in order to back out of the deal entirely. This violates trust with collectors.


We have fixed this problem by adding the following code to `createReserveAuction`:
```solidity
        // This check must be after _transferToEscrow in case auto-settle was required
        if (nftContractToTokenIdToAuctionId[nftContract][tokenId] != 0) {
          revert NFTMarketReserveAuction_Already_Listed(nftContractToTokenIdToAuctionId[nftContract][tokenId]);
        }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a multi‑auction creation flaw in the NFT market reserve auction contract. The contract allows the owner of an NFT to invoke the createReserveAuction function multiple times for the same token identifier without any guard that prevents a second listing from overwriting the first. The root cause lies in the fact that the function transfers the NFT to escrow before checking whether an auction already exists for that (nftContract, tokenId) pair; the mapping nftContractToTokenIdToAuctionId is then overwritten with the new auction identifier. An attacker can exploit this by calling createReserveAuction twice in quick succession, for example using a malicious contract to ensure no bids are placed between the two calls. After the second auction is created, the mapping points to the newest auction, while the first auction still exists in storage. The attacker (or the original seller) can then cancel the first auction and subsequently cancel the second auction. When the second auction is cancelled, any bid that was placed on it is automatically refunded to the bidder, but because the contract’s cancellation logic assumes only one active auction per token, the escrowed funds become permanently locked in the contract with no public function to retrieve them. This results in bidders losing access to their deposited ETH, effectively “funds disappearing” from their perspective. The impact is high: bidders’ assets are stuck in escrow, sellers can back out of a sale after receiving bids by simply creating and cancelling a second auction, and the trust model of the marketplace is broken. The condition under which this occurs is when the NFT owner (or any address with permission to list) creates more than one auction for the same token before a bid is placed. Users, collectors, and the protocol’s reputation are affected because bids appear to be accepted, yet the funds are never returned. The issue was discovered during a formal audit (Code4rena) by reviewing the createReserveAuction implementation and noticing that the existence check was placed after the escrow transfer, allowing the overwrite. It is subtle because the function otherwise behaves correctly for a single listing, and the overwritten auction identifier is not emitted in an obvious warning, making the problem easy to miss in manual testing. The bug belongs to the class of state‑inconsistency or double‑listing vulnerabilities, where contract state can be unintentionally overwritten, leading to loss of funds and broken business logic. To remediate, the contract should enforce a check that no active auction exists for the given NFT before transferring the token to escrow, reverting with a clear error if the mapping already contains a non‑zero auction identifier. This prevents multiple concurrent auctions for the same asset and ensures that escrowed funds can always be recovered through the normal settlement flow.
