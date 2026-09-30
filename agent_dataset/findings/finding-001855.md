---
id: 1855
severity: "High"
---

# No one can sell TaxTokensReceipts NFT receipt to the buy order The protocol has acknowledged this issue. Found by 0x37, KiroBrejka, bbl4de, dimulski, xiaoming90

## Description

Internal pre-conditions  
External pre-conditions  
Attack Path  
The TaxTokensReceipts NFT receipt exist to allow FOT to be used within the Debita ecosystem. If users have any tokens that charge a tax/fee on transfer, they must deposit them into the TaxTokensReceipts NFT receipt and use the NFT within the Debita ecosystem.  
The new Debita protocol has a new feature called ”Buy Order” or ”Limit Order” that allows users to create buy orders, providing a mechanism for injecting liquidity to purchase specific receipts at predetermined ratios. The receipts include the TaxTokensReceipts NFT receipt.  
Assume that Bob creates a new Buy Order to purchase TaxTokensReceipts NFT receipt. Alice, the holder of TaxTokensReceipts NFT receipt, decided to sell it to Bob's Buy Order. Thus, she called the buyOrder.sellNFT() function, and Line 99 below will attempt to transfer Alice's TaxTokensReceipts NFT receipt to the Buy Order contract.  
contracts/contracts/buyOrders/buyOrder.sol#L99  
File: buyOrder.sol  
```solidity
092: function sellNFT(uint receiptID) public {
093:     require(buyInformation.isActive, "Buy order is not active");
094:     require(
095:         buyInformation.availableAmount > 0,
096:         "Buy order is not available"
097:     );
098:
099:     IERC721(buyInformation.wantedToken).transferFrom(
100:         msg.sender,
101:         address(this),
102:         receiptID
103:     );
```
However, the transfer will always revert because the transfer function has been overwritten, as shown below. The transfer function has been overwritten to only allow the transfer to proceed if the to or from involves the following three (3) contracts:  
1. Borrow Order Contract  
2. Lend Order Contract  
3. Loan Contract  
Since neither the Buy Order contract nor the seller (Alice) is the above three contracts, the transfer will always fail. Thus, there is no way for anyone to sell their TaxTokensReceipts NFT receipt to the buy order. Thus, this feature is effectively broken.  
contracts/contracts/Non-Fungible-Receipts/TaxTokensReceipts/TaxTokensReceipt.sol#L98  
File: TaxTokensReceipt.sol  
```solidity
093: function transferFrom(
094:     address from,
095:     address to,
096:     uint256 tokenId
097: ) public virtual override(ERC721, IERC721) {
098:     bool isReceiverAddressDebita = IBorrowOrderFactory(borrowOrderFactory)
099:         .isBorrowOrderLegit(to) ||
100:         ILendOrderFactory(lendOrderFactory).isLendOrderLegit(to) ||
101:         IAggregator(Aggregator).isSenderALoan(to);
102:     bool isSenderAddressDebita = IBorrowOrderFactory(borrowOrderFactory)
103:         .isBorrowOrderLegit(from) ||
104:         ILendOrderFactory(lendOrderFactory).isLendOrderLegit(from) ||
105:         IAggregator(Aggregator).isSenderALoan(from);
106:     // Debita not involved --> revert
107:     require(
108:         isReceiverAddressDebita || isSenderAddressDebita,
109:         "TaxTokensReceipts: Debita not involved"
110:     );
```
Medium. Core protocol functionality (Buy Order/Limit Order) is broken.

## Proof of Concept

no poc

## Recommendation

Buy Order contract must be authorized to transfer TaxTokensReceipt NFT as it is also part of the Debita protocol.  
```solidity
function transferFrom(
    address from,
    address to,
    uint256 tokenId
) public virtual override(ERC721, IERC721) {
    bool isReceiverAddressDebita = IBorrowOrderFactory(borrowOrderFactory)
        .isBorrowOrderLegit(to) ||
        ILendOrderFactory(lendOrderFactory).isLendOrderLegit(to) ||
        IBuyOrderFactory(buyOrderFactory).isBuyOrderLegit(to) ||
        IAggregator(Aggregator).isSenderALoan(to);
    bool isSenderAddressDebita = IBorrowOrderFactory(borrowOrderFactory)
        .isBorrowOrderLegit(from) ||
        ILendOrderFactory(lendOrderFactory).isLendOrderLegit(from) ||
        IBuyOrderFactory(buyOrderFactory).isBuyOrderLegit(from) ||
        IAggregator(Aggregator).isSenderALoan(from);
    // Debita not involved --> revert
    require(
        isReceiverAddressDebita || isSenderAddressDebita,
        "TaxTokensReceipts: Debita not involved"
    );
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the transfer logic of the TaxTokensReceipts NFT, which is used to represent tax‑bearing tokens inside the Debita ecosystem. The contract overrides the standard ERC721 transferFrom function and restricts transfers to only those where either the sender or the receiver is one of three specific Debita contracts: a Borrow Order contract, a Lend Order contract, or a Loan contract. The newly introduced Buy Order (or Limit Order) feature creates a separate Buy Order contract that is intended to purchase these NFT receipts from users. When a holder calls buyOrder.sellNFT() the function attempts to move the NFT from the seller to the Buy Order contract via the overridden transferFrom. Because the Buy Order contract is not included in the whitelist check, the require statement in transferFrom fails and the transaction reverts with the message "TaxTokensReceipts: Debita not involved". Consequently, no user can sell a TaxTokensReceipts NFT to a buy order, rendering the buy‑order liquidity mechanism inoperable. The impact is that users expecting to sell their receipt for liquidity receive no transaction execution, their balances remain unchanged, and the protocol’s advertised feature of automated market making for tax‑token receipts is effectively broken. This condition occurs whenever a sellNFT call is made against a TaxTokensReceipts NFT while the Buy Order contract is the intended recipient. The affected parties are token holders who wish to liquidate their receipts, liquidity providers relying on the buy‑order market, and the overall Debita protocol which loses a core functionality. The issue was identified during a security audit when the auditors examined the transferFrom implementation and noticed that the Buy Order contract was omitted from the allowed address list. It can be hard to spot because the code follows a typical pattern of restricting transfers to known contracts, and the omission of the new contract does not raise a compiler warning. To remediate the problem, the transferFrom function should be extended to recognise the Buy Order contract (for example by adding an IBuyOrderFactory.isBuyOrderLegit check) or by redesigning the whitelist to include any contract that is part of the Debita protocol, thereby allowing the NFT to be transferred to a buy order. This change restores the intended behaviour where a user can sell a receipt to a buy order, enabling the protocol’s liquidity injection mechanism to function as designed.
