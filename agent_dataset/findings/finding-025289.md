---
id: 25289
severity: "Low/Info"
---

# Overflow check in PowerToken._divideUp is unnecessary

## Description

The [PowerToken._divideUp](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/PowerToken.sol#L427-L437>) function checks if a result of a multiplication "wrapped" around the maximum number, i.e. if it silently overflowed:

```solidity
z = (x * ONE) + y;
if (z < x) revert DivideUpOverflow();
```

Because calculation of z is not unchecked, the condition z < x will never be true, since solidity 0.8 checks and reverts on overflow.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the line checking the z < x condition.
