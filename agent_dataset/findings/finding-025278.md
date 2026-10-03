---
id: 25278
severity: "Low/Info"
---

# Custom error for overflowing the total principal is not raised

## Description

In the [MToken._mint](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MToken.sol#L217-L233>) function, there's a check to make sure the total principal doesn't become larger than a uint112: if ( principalOfTotalEarningSupply + _getPrincipalAmountRoundedDown(totalNonEarningSupply) >= type(uint112).max

```solidity
) {
revert OverflowsPrincipalOfTotalSupply();
}
```

Inside the condition, we're adding two uint112 numbers, which will panic overflow if the result is greater than type(uint112).max (solidity 0.8 is being used). For this reason, the error inside the if statement will never actually be reached.

## Proof of Concept

No PoC provided.

## Recommendation

Cast one of the numbers to uint256 to prevent the addition from panic overflowing:

```solidity
if ( uint256(principalOfTotalEarningSupply) +
_getPrincipalAmountRoundedDown(totalNonEarningSupply) >= type(uint112).max
) {
revert OverflowsPrincipalOfTotalSupply();
}
```
