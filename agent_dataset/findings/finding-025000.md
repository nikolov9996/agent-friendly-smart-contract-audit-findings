---
id: 25000
severity: "Low/Info"
---

# Significant rounding error in whitelist discount that could be avoided

## Description



## Proof of Concept

## Vulnerability Detail

The resolver fee is discounted by doing the following:

```solidity
if (isWhitelisted) {
    resolverFee = resolverFee * whitelistDiscountNumerator / _BASE_1E2;
}
```

As can be seen, it is applied in the `resolverFee` itself, which just has `1e5` precision.

## Code Snippet

[https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/AmountGetterWithFee.sol#L88](<https://github.com/sherlock-audit/2025-04-1inch/blob/main/limit-order-protocol/contracts/extensions/AmountGetterWithFee.sol#L88>)

## Recommendation

In `_getMakingAmount()` it may not be possible to apply the fix directly because it is dividing by the `resolverFee`. Probably adding a precision multiplier would be better. For example, scaling it to 1e18 fixes the issue: Suppose the fee is 9999, taking amount is 10_000 USD, share is `50%`. Scaled fee = resolver fee * 1e18 / 1e5 / 2 = 9999 * 1e18 / 1e5 / 2 = 4.9995e16 (notice how the 0.5 is kept). Fixed total resolver fee = takingAmount * resolverFee / 1e18 = 10_000e6 * 4.9995e16 / 1e18 = 499.95e6. The 0.05 USD component would be lost without scaling the fee. It may not be much but with enough volume it adds up.
