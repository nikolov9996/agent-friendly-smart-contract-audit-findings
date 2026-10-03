---
id: 25294
severity: "Crit/High"
---

# Validator signature with zero timestamp can always be replayed

## Description

When calling [MinterGateway.updateCollateral](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MinterGateway.sol#L136-L143l>), an array of timestamps gets passed. That is because the digest signed by a validator includes an updating timestamp.

The minimum timestamp between the signatures will be used as the new collateral update timestamp. This is used to check for staleness, which also has the side effect of preventing replaying a set of signatures:

```solidity
function _updateCollateral(address minter_, uint240 amount_, uint40 newTimestamp_) internal {
    uint40 lastUpdateTimestamp_ = _minterStates[minter_].updateTimestamp;
    // MinterGateway already has more recent collateral update
    if (newTimestamp_ < lastUpdateTimestamp_) revert StaleCollateralUpdate(newTimestamp_, lastUpdateTimestamp_);
    _minterStates[minter_].collateral = amount_;
    _minterStates[minter_].updateTimestamp = newTimestamp_;
}
```

The issue arises when a timestamp signed by a validator is zero. This is explicitly allowed by the validator signature verification, which ignores zero values:

```solidity
// Find minimum between all valid timestamps for valid signatures. minTimestamp_ = UIntMath.min40IgnoreZero(minTimestamp_,

    UIntMath.safe40(timestamps_[index_]));
```

In the extreme scenario where every validator signature of the array has a zero timestamp, minTimestamp_ will be block.timestamp, which will always pass the staleness check.

This means that an array of signatures with zero timestamps can be replayed as many times as a minter wants, thus achieving a way for updating its collateral to that same value in the future, regardless of whether or not that's still true in the off-chain world. A minter could do the following:

1. Add a very large amount of real world collateral. Let's say $10M.
2. Call updateCollateral with the right amount. Let's assume validators will have signed with a zero timestamp, which is explicitly allowed by the protocol.
3. Redeem the entire real world collateral.
4. Call updateCollateral by replaying the original validator signatures. The protocol will still think the minter has all the collateral.
5. Mint the maximum allowed amount of MToken. Sell them somewhere at market price. In a less extreme scenario where only 1 validator signs with a zero timestamp, we can still say that this specific signature can be reused anytime in the future, as long as the same collateral value is being used and that validator continues being approved by the TTG. The previous scenario can still be achieved if a minter rightfully calls updateCollateral multiple times with the same amount and rotates the validators until they finally get enough zero timestamp signatures from different validators.

## Proof of Concept

No PoC provided.

## Recommendation

Revert the signature verification if a timestamp is zero, by adding the following line to _verifyValidatorSignatures's loop: if (timestamps_[index_] == 0) revert ZeroTimestamp();
