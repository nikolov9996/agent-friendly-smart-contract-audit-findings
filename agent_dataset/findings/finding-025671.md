---
id: 25671
severity: "Crit/High"
---

# burnSharesToWithdrawEarnings burns before math, causing the share value to increase

## Description



## Proof of Concept

## Vulnerability Detail

When `burnSharesToWithdrawEarnings` burns shares and subsequently calculates the principal per share, the share amount is reduced but the principal remains the same, leading to a decrease in the `sharesExchangeRateInverse`, which increases the principal paid.

Principal is calculated using [_valueOfUnderlying](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L324>), where the formula is:

```solidity
uint256 principalTokenValueToWithdraw = (amount * 1e36) / sharesExchangeRateInverse();
```

The problem arises in [sharesExchangeRateInverse](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L277>) which uses the reduced share count:

```solidity
return  1e72 / sharesExchangeRate();
```

Where [sharesExchangeRate](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L262>) is defined as:

```solidity
rate_ = (poolTotalEstimatedValue * 1e36) / poolSharesToken.totalSupply();
```

Example:

- 1k shares and 10k principal.

1. Alice withdraws 20% of the shares.
2. 200 shares are burned, reducing the supply to 800.
3. Calculation for principal:

`rate_ = (10_000e18  1e36) / 800e18 = 1.25e37`* `sharesExchangeRateInverse = 1e72 / 1.25e37 = 8e34` `principalTokenValueToWithdraw = 200e18 `*` 1e36 / 8e34 = 2500e18`

4. Alice withdraws 25% of the pool's principal, despite owning only 20% of the shares.

## Impact

This flaw results in incorrect calculations, allowing some users to withdraw more than their fair share, potentially leading to insolvency.

## Code Snippet

```solidity
poolSharesToken.burn(msg.sender, _amountPoolSharesTokens);
uint256 principalTokenValueToWithdraw = _valueOfUnderlying(
    _amountPoolSharesTokens,
    sharesExchangeRateInverse()
);
```

## Recommendation

To ensure accurate withdrawal amounts, calculate `principalTokenValueToWithdraw` before burning the shares.
