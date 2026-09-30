---
id: 19666
severity: "High"
---

# `ArtPiece.totalVotesSupply` and `ArtPiece.quorumVotes` are incorrectly calculated due to inclusion of the inaccessible voting powers of the NFT that is being auctioned at the moment when an art piece is created

## Description

In this protocol, art pieces are uploaded, voted on by the community and auctioned. Being the highest-voted art piece is not enough to go to auction, and that art piece also must reach the quorum.

The quorum for the art piece is determined according to the total vote supply when the art piece is created. This total vote supply is calculated according to the current supply of the `erc20VotingToken` and `erc721VotingToken`. `erc721VotingTokens` have [weight](https://github.com/code-423n4/2023-12-revolutionprotocol/blob/d42cc62b873a1b2b44f57310f9d4bbfdd875e8d6/packages/revolution/src/CultureIndex.sol#L44C3-L45C44) compared to regular `erc20VotingTokens` and ERC721 tokens give users much more voting power.

```solidity
file: CultureIndex.sol
function createPiece ...{
    // ...
    newPiece.totalVotesSupply = _calculateVoteWeight(
        erc20VotingToken.totalSupply(),
        erc721VotingToken.totalSupply() //@audit-issue This includes the erc721 token which is currently on auction. No one can use that token to vote on this piece.
    );
    // ...
    newPiece.quorumVotes = (quorumVotesBPS * newPiece.totalVotesSupply) / 10_000; //@audit quorum votes will also be higher than it should be.
    // ...
}
    
_calculateVoteWeight function:
    
function _calculateVoteWeight(uint256 erc20Balance, uint256 erc721Balance) internal view returns (uint256) {
    return erc20Balance + (erc721Balance * erc721VotingTokenWeight * 1e18);
}
```

As I mentioned above, `totalVotesSupply` and `quorumVotes` of an art piece are calculated when the art piece is created based on the total supplies of the erc20 and erc721 tokens.

However, there is an important logic/context issue here.  
This calculation includes the erc721 verbs token which is **currently on auction** and sitting in the `AuctionHouse` contract. The voting power of this token can never be used for that art piece because:

  1. `AuctionHouse` contract obviously can not vote.
  2. The future buyer of this NFT also can not vote since users’ right to vote is determined based on the [creation block](https://github.com/code-423n4/2023-12-revolutionprotocol/blob/d42cc62b873a1b2b44f57310f9d4bbfdd875e8d6/packages/revolution/src/CultureIndex.sol#L313C26-L313C77) of the art piece.

In the end, totally inaccessible voting powers are included when calculating `ArtPiece.totalVotesSupply` and `ArtPiece.quorumVotes`, which results in incorrect quorum requirements and makes it harder to reach the quorum.

## Proof of Concept

Let’s assume that:  
-The current `erc20VotingToken` supply is 1000 and it won’t change for this scenario.  
-The weight of `erc721VotingToken` is 100.  
-`quorumVotesBPS` is 5000 (50% quorum required)

**Day 0: Protocol Launched**

  1. Users started to upload their art pieces.
  2. There is no NFT minted yet.
  3. The total votes supply for all of these art pieces is 1000.

**Day 1: First Mint**

  1. One of the art pieces is chosen.
  2. The art piece is minted in `VerbsToken` contract and transferred to `AuctionHouse` contract.
  3. The auction has started.
  4. `erc721VotingToken` supply is 1 at the moment.
  5. Users keep uploading art pieces for the next day’s auction.
  6. For these art pieces uploaded on day 1:  
`totalVotesSupply` is 1100  
`quorumVotes` is 550  
**Accessible vote supply is still 1000**.
  7. According to accessible votes, the quorum rate is 55% not 50.

**Day 2: Next Day**

  1. The auction on the first day is concluded and transferred to the buyer.
  2. The next `verbsToken` is minted and the auction is started.
  3. `erc721VotingToken` supply is 2.
  4. Users keep uploading art pieces for the next day’s auction.
  5. For these art pieces uploaded on day 2:  
`totalVotesSupply` is 1200  
`quorumVotes` is 600  
**Accessible vote supply is 1100**. (1000 + 100 from the buyer of the first NFT)
  6. The actual quorum rate for these art pieces is ~54.5% (600 / 1100).

_NOTE: The numbers used here are just for demonstration purposes. The impact will be much much higher if the`erc721VotingToken` weight is a bigger value like 1000._

## Recommendation

I strongly recommend subtracting the voting power of the NFT currently on auction when calculating the vote supply of the art piece and the quorum requirements.
    
```solidity
// Note: You will also need to store auctionHouse contract address
in this contract.
address auctionHouse;
    
function createPiece () {
    ...

    newPiece.totalVotesSupply = _calculateVoteWeight(
        erc20VotingToken.totalSupply(),
        // Note: We don't subtract 1 as fixed amount in case of auction house being paused and not having an NFT at that moment. We only subtract if there is an ongoing auction. 
        erc721VotingToken.totalSupply() - erc721VotingToken.balanceOf(auctionHouse)
    );

    ...
}
```

This means that at worst you could directly use...
What the finding also implies, is that if...

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an incorrect calculation of the total voting power and the quorum threshold for each art piece when it is created. The contract determines the total vote supply by adding the ERC20 token supply to the weighted ERC721 token supply. However, the calculation does not exclude the ERC721 token that is simultaneously transferred to the AuctionHouse contract for the piece that is being auctioned. Because the AuctionHouse contract cannot vote and the future buyer of the NFT is only granted voting rights from the block at which the art piece was created, the voting power attached to that NFT is permanently inaccessible for the newly created piece. As a result, the stored totalVotesSupply value includes voting weight that no participant can actually exercise, and the quorumVotes value, which is derived from totalVotesSupply, is inflated. When the community casts votes, the observable vote count may appear sufficient, but the protocol still rejects the piece because the reachable voting power is lower than the recorded quorum requirement. This mismatch makes it harder or even impossible for an art piece to satisfy the quorum, causing auctions to stall and potentially locking funds that would otherwise be released. The issue occurs each time a new NFT is minted and immediately placed in the AuctionHouse at the moment of piece creation. It affects all participants who rely on the voting mechanism – artists, voters, and anyone with funds locked in the auction process. The problem was discovered during a manual audit that examined the logic of vote weight calculation and identified that the totalSupply of the ERC721 token was used without filtering out tokens held by the auction contract. The bug is subtle because the totalSupply function returns a correct numeric value, and the UI may display a quorum percentage that seems achievable, masking the fact that part of the supply is unusable. To remediate the issue, the contract should compute the vote weight by subtracting the balance of the ERC721 token held by the AuctionHouse (or otherwise exclude any tokens that cannot vote at the creation block) before applying the weight multiplier and deriving the quorum. This adjustment restores the alignment between the recorded quorum and the actually available voting power, ensuring that the protocol’s business logic for reaching quorum and triggering auctions functions as intended.
