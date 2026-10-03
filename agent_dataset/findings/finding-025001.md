---
id: 25001
severity: "Low/Info"
---

# Taker fee is underestimated due to incorrect fee calculation

## Description



## Proof of Concept

## Vulnerability Detail

The taker fee is calculated by picking up the maker amount and multiplying by (1 + fee). The maker amount is the amount the user receives. Consider the following example: Assume that the ratio between the maker and taker assets is the same. The taker wants a making amount of 1000, paying a fee of `1000 * 10% = 100`, so the taking amount is 1100. This means that effectively, the taker pays a fee of `100 / 1100` = 9.1%`, as they pay 1100 and receive 1000.

Same goes for the inverse calculation.

## Impact

Fee is smaller than intended.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/AmountGetterWithFee.sol#L33-L37](<https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/AmountGetterWithFee.sol#L33-L37>)

[https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/AmountGetterWithFee.sol#L55-L60](<https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/AmountGetterWithFee.sol#L55-L60>)

## Recommendation

The correct implementations are:

```Solidity
takingAmount = makerAmount / (1 - feeRate)
makerAmount = takingAmount * (1 - feeRate)
```
