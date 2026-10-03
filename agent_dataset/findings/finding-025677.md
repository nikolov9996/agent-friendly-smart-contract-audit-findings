---
id: 25677
severity: "Crit/High"
---

# liquidateDefaultedLoanWithIncentive sends the collateral to the wrong account

## Description



## Proof of Concept

## Vulnerability Detail

[liquidateDefaultedLoanWithIncentive](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L422>) is intended to liquidate bids, where liquidators pay off the debt and receive the collateral. However, currently the collateral is sent to the lender - LCG, because [lenderCloseLoanWithRecipient](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/TellerV2.sol#L738-L774>) includes `msg.sender` as its second parameter but does not utilize it:

```solidity
    function lenderCloseLoanWithRecipient(uint256 _bidId, address _collateralRecipient) external {
        _lenderCloseLoanWithRecipient(_bidId, _collateralRecipient);
    }

    function _lenderCloseLoanWithRecipient(uint256 _bidId, address _collateralRecipient) internal acceptedLoan(_bidId, "lenderClaimCollateral") {
        require(isLoanDefaulted(_bidId), "Loan must be defaulted.");

        Bid storage bid = bids[_bidId];
        bid.state = BidState.CLOSED;

        address sender = _msgSenderForMarket(bid.marketplaceId);
        require(sender == bid.lender, "Only lender can close loan");

        //@audit we directly call `lenderClaimCollateral`
        collateralManager.lenderClaimCollateral(_bidId);
    }
```

[lenderClaimCollateral](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/CollateralManager.sol#L271-L283>) in its place withdraws the collateral directly to the lender - LCG, without updating `totalPrincipalTokensRepaid`. Some effects:

- Liquidators will gain 0 profits, so they will not liquidate.
- LPs suffer losses as liquidations are not carried out, and returned collateral from liquidations is not accrued as `totalPrincipalTokensRepaid`, increasing utilization, eventually bricking the contract.

## Impact

Liquidators will not be incentivized to liquidate and incorrect accounting occurs inside LCG.

## Code Snippet

```solidity
    function _lenderCloseLoanWithRecipient(
        uint256 _bidId,
        address _collateralRecipient // @audit never used
    ) internal acceptedLoan(_bidId, "lenderClaimCollateral") {
        require(isLoanDefaulted(_bidId), "Loan must be defaulted.");

        Bid storage bid = bids[_bidId];
        bid.state = BidState.CLOSED;

        address sender = _msgSenderForMarket(bid.marketplaceId);
        require(sender == bid.lender, "Only lender can close loan");

        collateralManager.lenderClaimCollateral(_bidId);
    }
```

## Recommendation

Ensure [_lenderCloseLoanWithRecipient](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/TellerV2.sol#L745-L755>) sends the funds to `_collateralRecipient`.
