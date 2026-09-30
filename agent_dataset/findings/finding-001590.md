---
id: 1590
severity: "High"
---

# Creators can steal sale revenue from owners’ sales

## Description

```solidity
[NFTMarketCreators.sol#L158-L160](https://github.com/code-423n4/2022-02-foundation/blob/a03a7e198c1dfffb1021c0e8ec91ba4194b8aa12/contracts/mixins/NFTMarketCreators.sol#L158-L160)  
[NFTMarketCreators.sol#L196-L198](https://github.com/code-423n4/2022-02-foundation/blob/a03a7e198c1dfffb1021c0e8ec91ba4194b8aa12/contracts/mixins/NFTMarketCreators.sol#L196-L198)  
[NFTMarketCreators.sol#L97-L99](https://github.com/code-423n4/2022-02-foundation/blob/a03a7e198c1dfffb1021c0e8ec91ba4194b8aa12/contracts/mixins/NFTMarketCreators.sol#L97-L99)  

According to the [`README.md`](https://github.com/code-423n4/2022-02-foundation/blob/4d8c8931baffae31c7506872bf1100e1598f2754/README.md?plain=1#L21):

> All sales in the Foundation market will pay the creator 10% royalties on secondary sales. This is not specific to NFTs minted on Foundation, it should work for any NFT. If royalty information was not defined when the NFT was originally deployed, it may be added using the Royalty Registry which will be respected by our market contract.

Using the Royalty Registry an owner can decide to change the royalty information right before the sale is complete, affecting who gets what.
```

## Proof of Concept

```solidity
// 4th priority: getRoyalties override
              if (recipients.length == 0 && nftContract.supportsERC165Interface(type(IGetRoyalties).interfaceId)) {
                try IGetRoyalties(nftContract).getRoyalties{ gas: READ_ONLY_GAS_LIMIT }(tokenId) returns (
                  address payable[] memory _recipients,
                  uint256[] memory recipientBasisPoints
                ) {
                  if (_recipients.length > 0 && _recipients.length == recipientBasisPoints.length) {
                    bool hasRecipient;
                    for (uint256 i = 0; i < _recipients.length; ++i) {
                      if (_recipients[i] != address(0)) {
                        hasRecipient = true;
                        if (_recipients[i] == seller) {
                          return (_recipients, recipientBasisPoints, true);
```
When `true` is returned as the final return value above, the following code leaves `ownerRev` as zero because `isCreator` is `true`.
```solidity
          uint256 ownerRev
        )
      {
        bool isCreator;
        (creatorRecipients, creatorShares, isCreator) = _getCreatorPaymentInfo(nftContract, tokenId, seller);
    
        // Calculate the Foundation fee
        uint256 fee;
        if (isCreator && !_nftContractToTokenIdToFirstSaleCompleted[nftContract][tokenId]) {
          fee = PRIMARY_FOUNDATION_FEE_BASIS_POINTS;
        } else {
          fee = SECONDARY_FOUNDATION_FEE_BASIS_POINTS;
        }
    
        foundationFee = (price * fee) / BASIS_POINTS;
    
        if (creatorRecipients.length > 0) {
          if (isCreator) {
            // When sold by the creator, all revenue is split if applicable.
            creatorRev = price - foundationFee;
          } else {
            // Rounding favors the owner first, then creator, and foundation last.
            creatorRev = (price * CREATOR_ROYALTY_BASIS_POINTS) / BASIS_POINTS;
            ownerRevTo = seller;
            ownerRev = price - foundationFee - creatorRev;
          }
        } else {
          // No royalty recipients found.
          ownerRevTo = seller;
          ownerRev = price - foundationFee;
        }
      }
```
In addition, if the index of the seller in `_recipients` is greater than `MAX_ROYALTY_RECIPIENTS_INDEX`, then the seller is omitted from the calculation and gets zero (`_sendValueWithFallbackWithdraw()` doesn’t complain when it sends zero).
```solidity
            uint256 maxCreatorIndex = creatorRecipients.length - 1;
            if (maxCreatorIndex > MAX_ROYALTY_RECIPIENTS_INDEX) {
              maxCreatorIndex = MAX_ROYALTY_RECIPIENTS_INDEX;
            }
```
This issue does a lot of damage because the creator can choose whether and when to apply it on a sale-by-sale basis. Two other similar, but separate, exploits are available for the other blocks in `_getCreatorPaymentInfo()` that return arrays but they either require a malicious NFT implementation or can only specify a static seller for which this will affect things. In all cases, not only may the seller get zero dollars for the sale, but they’ll potentially owe a lot of taxes based on the ‘sale’ price. The attacker may or may not be the creator - creators can be bribed with kickbacks.

## Recommendation

```solidity
Always calculate owner/seller revenue separately from royalty revenue.
```
This is a great discovery and a creative way for creators to abuse the system, stealing funds from a secondary sale. Thank you for reporting this.

It’s a difficult one for us to address. We want to ensure that NFTs minted on our platform as a split continue to split revenue from the initial sale. We were using `isCreator` from `_getCreatorPaymentInfo` as our way of determining if all the revenue from a sale should go to the royalty recipients, which is a split contract for the use case we are concerned about here.

The royalty override makes it easy for a creator to choose to abuse this feature at any time. So that was our primary focus for this fix.

This is the change we have made in `_getFees`:
```solidity
        bool isCreator = false;
        // lookup for tokenCreator
        try ITokenCreator(nftContract).tokenCreator{ gas: READ_ONLY_GAS_LIMIT }(tokenId) returns (
          address payable _creator
        ) {
          isCreator = _creator == seller;
        } catch // solhint-disable-next-line no-empty-blocks
        {
          // Fall through
        }
    
        (creatorRecipients, creatorShares) = _getCreatorPaymentInfo(nftContract, tokenId);
```
Since the royalty override is only considered in `_getCreatorPaymentInfo` we are no longer vulnerable to someone adding logic after the NFT has been released to try and rug pull the current owner(s).

It is still possible for someone to try and abuse this logic, but to do so they must have built into the NFT contract itself a way to lie about who the `tokenCreator` is before the time of a sale. If we were to detect this happening, we would moderate that collection from the Foundation website. Additionally we will think about a longer term solution here so that this type of attack is strictly not possible with our market contract.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the way the Foundation marketplace contract determines how revenue from a secondary NFT sale is split between the seller (owner) and the royalty recipients. The contract calls a helper function that returns a list of royalty recipients and a flag called isCreator, which is set to true when the seller address matches the token creator address returned by an external token creator interface. If isCreator is true, the contract treats the entire sale price (minus the Foundation fee) as creator royalty revenue and assigns zero to the owner revenue variable. Because the royalty information can be overridden through the Royalty Registry immediately before a sale, a creator can inject a royalty payload that lists the seller as a recipient, causing the isCreator flag to be true and the owner revenue to remain zero. In addition, the contract caps the number of royalty recipients it processes; if the seller’s index exceeds this cap, the seller is omitted from the payment loop, again resulting in a zero payout that is silently transferred without a revert. Consequently, a seller can receive no funds from a sale they have successfully completed, yet the transaction records the full sale price and may still generate tax obligations. The issue manifests only when the creator manipulates the royalty data at the moment of sale, which is a subtle condition that can easily escape notice because the contract does not emit an explicit error when the owner payout is zero and the transfer of zero ether succeeds silently. The problem was discovered during a manual audit of the fee‑calculation logic, where the interaction between the _getCreatorPaymentInfo helper and the getRoyalties override revealed that the revenue split logic was dependent on a mutable royalty flag rather than a fixed accounting rule. This class of bug can be described as a “royalty‑override revenue split flaw” where mutable royalty data can be abused to divert funds from the intended recipient. The impact includes direct loss of sale proceeds for the seller, potential tax complications, and erosion of trust in the marketplace’s fairness. To remediate the issue, the contract should compute owner revenue and creator royalty revenue independently of the isCreator flag, ensure that any royalty override cannot affect the owner’s entitlement, and enforce a strict separation between creator royalties and seller proceeds. In practice this means always calculating the seller’s share based on the sale price, subtracting only the Foundation fee and the explicitly declared royalty amounts, regardless of who the seller is, and preventing the royalty registry from being used to manipulate the payout after a sale has been initiated.
