---
id: 25673
severity: "Crit/High"
---

# _sendOrEscrowFunds will brick LCG funds causing insolvency

## Description



## Proof of Concept

## Vulnerability Detail

[_sendOrEscrowFunds](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/TellerV2.sol#L916-L949>) has `try` and `catch`, where `try` attempts `transferFrom`, and if that fails, `catch` calls [deposit](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/TellerV2.sol#L942-L946>) on the **EscrowVault**. The try is implemented in case `transferFrom` reverts, ensuring the repay/liquidation call does not. If `transferFrom` reverts due to any reason, the tokens will be stored inside **EscrowVault**, allowing the lender to withdraw them at any time.

However, for LCG, if such a deposit happens, the tokens will be stuck inside **EscrowVault** since LCG lacks a withdraw implementation. The share price will still increase, as the next `if` will pass, but this will cause more damage to the pool. Not only did it lose capital, but it also became insolvent.

```solidity
    ILoanRepaymentListener(loanRepaymentListener).repayLoanCallback{gas: 80000}(
        _bidId,
        _msgSenderForMarket(bid.marketplaceId),
        _payment.principal,
        _payment.interest
    )
```

The pool is insolvent because the share value has increased, but the assets in the pool have not, meaning the last few LPs won't be able to withdraw.

## Impact

Fund loss for LCG and insolvency for the pool, as share price increases, but assets do not.

## Code Snippet

```solidity
IEscrowVault(escrowVault).deposit(
    lender,
    address(bid.loanDetails.lendingToken),
    paymentAmountReceived
);
```

## Recommendation

Implement the withdraw function inside LCG, preferably callable by anyone.
