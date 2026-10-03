---
id: 25302
severity: "Low/Info"
---

# Unrealized inflation calculation returns wrong value when balance reaches cap

## Description

The function [EpochBasedInflationaryVoteToken._getUnrealizedInflation](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/abstract/EpochBasedInflationaryVoteToken.sol#L258-L289>) calculates a given account's inflation which has not been added to their balance yet.

The inflation value gets incremented for each epoch the account/delegatee participated on. The issue is that if the inflatedBalance_ variable passes the type(uint240).max value, the function will return type(uint240).max, due to the following line:

```solidity
if (inflatedBalance_ >= type(uint240).max) return type(uint240).max;
```

Let's imagine an unrealistic scenario where the current balance of an account is type(uint240).max - 1, that inflation from 2 participations is still unrealized, and that participationInflation is 10%.

1. In the first participation loop, inflation_ is zero so inflatedBalance_ will not reach the cap. The newInflation_ value will be 10% of the initial balance, which also doesn't reach the cap.
2. In the second and last participation loop, inflatedBalance_ will now be 110% of the initial balance, which will reach the cap. Thus, type(uint240).max will be returned as the unrealized inflation value. It would have made more sense to force a cap on inflatedBalance_ by setting it to type(uint240).max and continuing the loop execution. This way, the final inflation value

being returned would end up being about 20% of the initial balance, which does seem to make more sense. That being said, and considering the usage of _getUnrealizedInflation throughout the contract, it does seem like there's no meaningful impact associated to this.

## Proof of Concept

No PoC provided.

## Recommendation

Consider changing the line mentioned above:

```solidity
if (inflatedBalance_ >= type(uint240).max) {
    inflatedBalance_ = type(uint240).max; }
```
