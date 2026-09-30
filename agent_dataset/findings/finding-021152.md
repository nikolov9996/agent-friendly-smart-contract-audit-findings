---
id: 21152
severity: "High"
---

# Function `refinanceFromLoanExecutionData`

## Description

The `refinanceFromLoanExecutionData()` function is used to refinance a loan from `LoanExecutionData`. It allows borrowers to use outstanding offers for new loans to refinance their current loan. This function essentially combines two actions: it processes the repayment for the previous loan and then emits a new loan.

The key difference is that the same NFT is used as collateral for the new loan, so it does not need to be transferred out of the protocol and then transferred back in. However, there is no check to ensure that the NFT id of the old loan matches the NFT id of the new execution data.

Therefore, the new loan may have a collateral NFT that does not match the NFT that the lender requested in their offers.
```solidity
/// @dev We first process the incoming offers so borrower gets the capital. After that, we process repayments.
///      NFT doesn't need to be transferred (it was already in escrow)
(uint256 newLoanId, uint256[] memory offerIds, Loan memory loan, uint256 totalFee) =
_processOffersFromExecutionData(
    borrower,
    executionData.principalReceiver,
    principalAddress,
    nftCollateralAddress,
    executionData.tokenId, // @audit No check if matched with loan.nftCollateralTokenId
    executionData.duration,
    offerExecution
);
```

## Proof of Concept

As we can see, `executionData.tokenId` is passed to the `_processOffersFromExecutionData()` function instead of `loan.nftCollateralTokenId`. This function performs all the checks to ensure that the lenders’ offers accept this NFT.
```solidity
function _processOffersFromExecutionData(
    address _borrower,
    address _principalReceiver,
    address _principalAddress,
    address _nftCollateralAddress,
    uint256 _tokenId,
    uint256 _duration,
    OfferExecution[] calldata _offerExecution
) private returns (uint256, uint256[] memory, Loan memory, uint256) {
  ...
  _validateOfferExecution(
      thisOfferExecution,
      _tokenId,
      offer.lender,
      offer.lender,
      thisOfferExecution.lenderOfferSignature,
      protocolFee.fraction,
      totalAmount
  );
  ...
}
```
Eventually, it calls the `_checkValidators()` function to check the NFT token ID.
```solidity
function _checkValidators(LoanOffer calldata _loanOffer, uint256 _tokenId) private {
    uint256 offerTokenId = _loanOffer.nftCollateralTokenId;
    if (_loanOffer.nftCollateralTokenId != 0) {
        if (offerTokenId != _tokenId) {
            revert InvalidCollateralIdError();
        }
    } else {
        uint256 totalValidators = _loanOffer.validators.length;
        if (totalValidators == 0 && _tokenId != 0) {
            revert InvalidCollateralIdError();
        } else if ((totalValidators == 1) && (_loanOffer.validators[0].validator == address(0))) {
            return;
        }
        for (uint256 i = 0; i < totalValidators;) {
            IBaseLoan.OfferValidator memory thisValidator = _loanOffer.validators[i];
            IOfferValidator(thisValidator.validator).validateOffer(_loanOffer, _tokenId, thisValidator.arguments);
            unchecked {
                ++i;
            }
        }
    }
}
```
However, since `executionData.tokenId` is passed in, an attacker could pass in a valid `tokenId` (an NFT id that will be accepted by all lender offers). But in reality, the `loan.nftCollateralTokenId` will be the NFT kept in escrow.

## Recommendation

Add a check to ensure that `executionData.tokenId` is equal to `loan.nftCollateralTokenId`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the refinanceFromLoanExecutionData function, which enables a borrower to refinance an existing loan by supplying a new set of loan execution data. The function reuses the NFT that is already held in escrow as collateral, avoiding a transfer step. However, the implementation does not verify that the token identifier supplied in the new execution data (executionData.tokenId) matches the identifier of the NFT that was originally locked for the old loan (loan.nftCollateralTokenId). Because the internal _processOffersFromExecutionData routine validates offers against the token identifier it receives, passing an arbitrary tokenId that satisfies the lenders' offer constraints allows the borrower to create a new loan that is ostensibly backed by a different NFT than the one actually held in escrow. This mismatch can be exploited by a malicious borrower who supplies a tokenId that is accepted by all lender offers, while the real collateral remains a different NFT or even an empty slot if the original loan used a validator‑based collateral model. The impact is that lenders believe they are lending against a specific NFT they approved, but the protocol records a loan secured by another asset, potentially resulting in loss of the intended collateral, misallocation of funds, and a breach of the accounting assumptions that tie each loan to a unique piece of collateral. The flaw manifests whenever refinanceFromLoanExecutionData is called, i.e., during any refinancing operation, and it affects all participants: lenders who placed offers, borrowers who refinance, and the protocol itself because the invariant that a loan’s collateral matches the NFT locked in escrow is violated. The issue was discovered during a security audit that examined the flow of data between the old loan structure and the new execution payload and noticed that the tokenId argument is forwarded without a consistency check. It is subtle because the UI typically shows the same NFT remaining in escrow, and there is no explicit error message; users may only notice that a loan was created with unexpected collateral or that a repayment does not release the expected NFT. To remediate the problem, the contract should enforce that executionData.tokenId equals loan.nftCollateralTokenId before processing offers, rejecting any attempt to refinance with a mismatched token identifier. This simple equality check restores the guarantee that the collateral recorded for the new loan is exactly the NFT that is physically held by the protocol, thereby aligning lender expectations with on‑chain reality and preventing the described misuse scenario.
