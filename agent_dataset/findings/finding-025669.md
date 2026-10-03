---
id: 25669
severity: "Medium"
---

# Issue #497 'Add parameter to lender accept bid for MaxMarketFee' from previous audit is still present

## Description



## Proof of Concept

## Vulnerability Detail

The vulnerability is well explain in the mentionedl link above, essentially any market owner may change the marketplace fee while frontrunning a borrower and getting more funds in return.

A PR with the fix was mentioned in the comments but it was never [merged](<https://github.com/teller-protocol/teller-protocol-v2/pull/81/files>).

From the [docs](<https://docs.sherlock.xyz/audits/judging/judging>), the issue is valid as long as there is not a `won't fix` label.

## Impact

Borrower pays more marketplace fees than expected due to malicious market owner.

## Code Snippet

[TellerV2::lenderAcceptBid()](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/TellerV2.sol#L481>)

```solidity
function lenderAcceptBid(uint256 _bidId)
    ...
{
    ...
    amountToMarketplace = bid.loanDetails.principal.percent(
        marketRegistry.getMarketplaceFee(bid.marketplaceId)
    ...
}
```

## Recommendation

The recommendation from issue [#497](<https://github.com/sherlock-audit/2023-03-teller-judging/issues/497>) are good:

> Add a timelock delay for setMarketFeePercent/setProtocolFee

allow lenders to specify the exact fees they were expecting as a parameter to lenderAcceptBid
