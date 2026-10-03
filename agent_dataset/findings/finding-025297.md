---
id: 25297
severity: "Low/Info"
---

# A sufficiently large collateral may break the maximum owed M calculation

## Description

In the [MinterGateway](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MinterGateway.sol>) contract, the updateCollateral function can set a collateral value to any value, provided the value is no larger than type(uint240).max and the data is signed by enough validators.

The maxAllowedActiveOwedMOf function will use the collateral value to assess if a minter is undercollateralized:

```solidity
function maxAllowedActiveOwedMOf(address minter_) public view returns
(uint256) {
    // NOTE: Since `mintRatio()` is capped at 10,000% (i.e. 1_000_000)
this cannot overflow.
unchecked {
    return _minterStates[minter_].isActive ? (uint256(collateralOf(minter_)) * mintRatio()) / ONE : 0;
}
}
```

The comment note in maxAllowedActiveOwedMOf is incorrect, because the multiplication of a large mintRatio with a large collateral can overflow a uint256.

In the unlikely scenario that validators allow a very odd and large collateral value, this multiplication will silently overflow due to the unchecked block, leading to a wrong calculation of the maximum allowed debt.

## Proof of Concept

No PoC provided.

## Recommendation

Remove the unchecked block in this situation to avoid a silent overflow. For better readability, consider raising a custom error instead of letting the compiler raise a panic error upon overflow.
