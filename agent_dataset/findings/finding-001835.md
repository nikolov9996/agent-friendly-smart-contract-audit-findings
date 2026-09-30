---
id: 1835
severity: "High"
---

# Lenders and borrowers can not

## Description

The incorrect logic in function veNFTAerodrome::getDataByReceipt() will cause the lenders and borrowers unable to claim liquidation token after the NFT auction is sold.
• The function DebitaV3Loan::claimCollateralAsNFTLender() allows the lenders to claim the liquidation token after the NFT collateral auction is sold.
• The function DebitaV3Loan::claimCollateralNFTAsBorrower() allows the borrower to claim the liquidation token in case of partial default.
• These two functions above call veNFTAerodrome::getDataByReceipt() to retrieve the liquidation token's decimals to calculate the payment amount.
• These two flows above can be reverted because of an unhandled case in the function veNFTAerodrome::getDataByReceipt(). The mentioned unhandled case is when there is no owner of the receipt token, such that ownerOf(receiptID) reverts because of non-existent token.

```solidity
function getDataByReceipt(
    uint receiptID
) public view returns (receiptInstance memory) {
    veNFT veContract = veNFT(nftAddress);
    veNFTVault vaultContract = veNFTVault(s_ReceiptID_to_Vault[receiptID]);
    uint nftID = vaultContract.attached_NFTID();
    IVotingEscrow.LockedBalance memory _locked = veContract.locked(nftID);
    uint _decimals = ERC20(_underlying).decimals();
    address manager = vaultContract.managerAddress();
    address currentOwnerOfReceipt = ownerOf(receiptID);
    receiptInstance memory receiptData = receiptInstance({
        receiptID: receiptID,
        attachedNFT: nftID,
        lockedAmount: uint(int(_locked.amount)),
        lockedDate: _locked.end,
        decimals: _decimals,
        vault: address(vaultContract),
        underlying: _underlying,
        OwnerIsManager: manager == currentOwnerOfReceipt
    });
    return receiptData;
}

function ownerOf(uint256 tokenId) public view virtual returns (address) {
    return _requireOwned(tokenId);
}

...

function _requireOwned(uint256 tokenId) internal view returns (address) {
    address owner = _ownerOf(tokenId);
    if (owner == address(0)) {
        revert ERC721NonexistentToken(tokenId);
    }
    return owner;
}
```

This state can be reached when the auction buyer withdraws veNFT by calling veNFTVault::withdraw(), which will burn the receipt token.

```solidity
function withdraw() external nonReentrant {
    IERC721 veNFTContract = IERC721(veNFTAddress);
    IReceipt receiptContract = IReceipt(factoryAddress);
    uint m_idFromNFT = attached_NFTID;
    address holder = receiptContract.ownerOf(receiptID);
    // RECEIPT HAS TO BE ON OWNER WALLET
    require(attached_NFTID != 0, "No attached nft");
    require(holder == msg.sender, "Not Holding");
    receiptContract.decrease(managerAddress, m_idFromNFT);
    delete attached_NFTID;
    // First: burn receipt
    IReceipt(factoryAddress).burnReceipt(receiptID);
    IReceipt(factoryAddress).emitWithdrawn(address(this), m_idFromNFT);
    // Second: send them their NFT
    veNFTContract.transferFrom(address(this), msg.sender, m_idFromNFT);
}

function burnReceipt(uint id) external onlyVault {
    _burn(id);
}
```

Internal pre-conditions
External pre-conditions
Attack Path
• A borrower deposits veNFT to veNFTVault by calling veNFTAerodrome::deposit(), effectively receives a Receipt token
• The borrower creates borrow offer with the Receipt token as collateral
• The borrow offer is matched with many lend offers
• The borrower does not pay debt for all lend offers before the deadline and a lender calls createAuctionForCollateral to create an auction for the collateral
• Auction is sold
• The auction buyer, now the current holder of the Receipt token, decides to withdraw the veNFT from the vault by calling veNFTVault::withdraw()
• At this time, both borrower and lenders can not claim liquidation token
• Loss of liquidation for both lenders and borrower

## Proof of Concept

Update the test testDefaultAndAuctionCall in file test/fork/Loan/ltv/OracleOneLenderLoanReceipt.t.sol as below:
```solidity
function testDefaultAndAuctionCall() public {
    MatchOffers();
    uint256[] memory indexes = allDynamicData.getDynamicUintArray(1);
    indexes[0] = 0;
    vm.warp(block.timestamp + 8640010);
    DebitaV3LoanContract.createAuctionForCollateral(0);
    DutchAuction_veNFT auction = DutchAuction_veNFT(DebitaV3LoanContract.getAuctionData().auctionAddress);
    DutchAuction_veNFT.dutchAuction_INFO memory auctionData = auction.getAuctionData();
    vm.warp(block.timestamp + (86400 * 10) + 1);
    address buyer = 0x5C235931376b21341fA00d8A606e498e1059eCc0;
    deal(AERO, buyer, 100e18);
    vm.startPrank(buyer);
    AEROContract.approve(address(auction), 100e18);
    auction.buyNFT();
    vm.stopPrank();
    address ownerOfNFT = receiptContract.ownerOf(receiptID);
    // buyer withdraws NFT
    vm.startPrank(ownerOfNFT);
    address vaultAddress = receiptContract.s_ReceiptID_to_Vault(receiptID);
    veNFTVault vault = veNFTVault(vaultAddress);
    vault.withdraw();
    // lender claim liquidation token
    vm.stopPrank();
    vm.expectRevert();
    DebitaV3LoanContract.claimCollateralAsLender(0);
}
```
Run the test and console shows:
Ran 1 test for test/fork/Loan/ltv/OracleOneLenderLoanReceipt.t.sol:DebitaAggregatorTest
[PASS] testDefaultAndAuctionCall() (gas: 3381044)

## Recommendation

1/ Update the function getDataByReceipt() to handle the case of non-existent token, instead of reverting.
2/ OR update the logic to fetch the decimals in functions claimCollateralAsNFTLender and claimCollateralNFTAsBorrower.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unchecked existence check for the receipt ERC721 token used as collateral in the liquidation flow of the Debita V3 loan protocol. When a veNFT auction is sold, the buyer becomes the holder of the receipt token and can later call veNFTVault.withdraw(), which burns the receipt token. The claim functions for lenders (claimCollateralAsNFTLender) and borrowers (claimCollateralNFTAsBorrower) rely on veNFTAerodrome.getDataByReceipt to obtain the token decimals needed for payment calculation. getDataByReceipt unconditionally calls ownerOf(receiptID) to retrieve the current owner, but if the receipt has been burned ownerOf reverts with ERC721NonexistentToken. Because this revert is not caught, the entire claim transaction aborts, leaving both lenders and borrowers unable to receive their liquidation tokens. From a user perspective the transaction simply fails, often showing a generic revert error or “transaction failed” message, and the expected liquidation token balance remains unchanged. The impact is that funds that should be distributed after liquidation become locked, breaking the protocol’s accounting assumptions and potentially causing loss of expected returns. The issue occurs only after the specific sequence where the auction buyer withdraws the veNFT after the auction, i.e., when the receipt token no longer exists. It was discovered during an audit when a test reproduced the failure by simulating the withdraw step followed by a claim attempt. The bug is hard to notice because the getDataByReceipt function appears to be a read‑only helper and the edge case of a burned receipt is not exercised in normal operation. Conceptually, the fix is to handle the non‑existent token case inside getDataByReceipt, for example by checking token existence before calling ownerOf or by providing a fallback value, or alternatively by obtaining the required decimals directly in the claim functions without depending on the receipt token. This class of bug falls under improper handling of external contract calls that may revert, leading to denial‑of‑service for legitimate users.
