---
id: 25295
severity: "Low/Info"
---

# Multiplication after division in StableEarnerRateModel leads to loss of precision

## Description

In the [StableEarnerRateModel.getSafeEarnerRate](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/rateModels/StableEarnerRateModel.sol#L69-L117>) function, there's a log calculation detailed in a comment:

```solidity
// 6. ln(1 + (totalActive * (delta_minterIndex - 1) / totalEarning)) * SECONDS_PER_YEAR / dt = earnerRate
```

The code implementation of the log argument calculation follows the comment, but using fixed point arithmetic with 12 decimals. The problem is that a division by 1e12 is immediately followed by a 1e12 multiplication: 1e12 + ((((uint256(totalActiveOwedM_) * (deltaMinterIndex_ - 1e12)) / 1e12) * 1e12) / totalEarningSupply_) That division combined with the multiplication should cancel out in real world math.

But because of integer division, this sets the first 12 decimals to zero.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the division and multiplication by 1e12.
