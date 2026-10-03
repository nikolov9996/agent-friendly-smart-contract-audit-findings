---
id: 25288
severity: "Low/Info"
---

# _checkAndIncrementNonce in ERC5805 raises a ReusedNonce error for non used nonces

## Description

The [ERC5805._checkAndIncrementNonce](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/abstract/ERC5805.sol#L49-L57>) function makes sure the nonce being used in a signature is the right one.

If it is, it increments it:

```solidity
function _checkAndIncrementNonce(address account_, uint256 nonce_)
internal {
    uint256 currentNonce_ = nonces[account_];
    if (nonce_ != currentNonce_) revert ReusedNonce(nonce_, currentNonce_);
    unchecked {
```

nonces[account_] = currentNonce_ + 1; // Nonce realistically cannot overflow.

```solidity
}
}
```

The error being raised when nonce_ != currentNonce_ is misleading. The if statement doesn't necessarily mean that the nonce_ value being used has been used in past signatures, rather it means that it is not the expected current nonce of the account.

For example, if the current nonce is 1 and the user signs the data with nonce 3, this should revert, but nonce 3 hasn't been used yet.

## Proof of Concept

No PoC provided.

## Recommendation

Consider renaming the error to more accurately describe the issue. For example, NotCurrentNonce.
