---
id: 25273
severity: "Low/Info"
---

# Code should not panic underflow

## Description

There's several places in the protocol where proper code validation is missing by, instead, relying on panic errors. This is not recommended behaviour as per [Solidity Docs](<https://docs.soliditylang.org/en/v0.8.23/control-structures.html#panic-via-assert-and-error-via-require>): Properly functioning code should never create a Panic, not even on invalid external input.

If this happens, then there is a bug in your contract which you should fix. Here are the instances that rely on panic errors caught during the review:

- [MToken._subtractEarningAmount](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MToken.sol#L303>)
- [MToken._subtractNonEarningAmount](<https://github.com/MZero-Labs/protocol/blob/3499f50ff3382729f3e59565b19386ba61ef8e36/src/MToken.sol#L316>)
- [ERC20Extended.transferFrom](<https://github.com/MZero-Labs/common/blob/4a37119f2da946c6d8ad7b9a70dfdd219225115b/src/ERC20Extended.sol#L86>)
- [DistributionVault.getClaimable](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/DistributionVault.sol#L141>)
- [PowerToken._divideUp](<https://github.com/MZero-Labs/ttg/blob/a8127901fa1f24a2e821cf4d9854a1aa6ac8088c/src/PowerToken.sol#L427>)

## Proof of Concept

No PoC provided.

## Recommendation

Raise proper errors instead of relying on panic.
