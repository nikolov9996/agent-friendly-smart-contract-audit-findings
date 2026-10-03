---
id: 25488
severity: "Low/Info"
---

# trimDuplicatePools() is very expensive, having O(n^2) complexity and could be simplified

## Description

[ammRouter:trimDuplicatePools()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMMRouter.sol#L848>) eliminates duplicate pools in the input by comparing every element of the array for duplicates, which is very expensive.

Note: the function is actually useless as it is impossible to add liquidity in duplicate pools. It would [revert](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMM.sol#L412>) with error "SANDWICH".

## Proof of Concept

No PoC provided.

## Recommendation

Force the user to input pool indexes ordered and if there are duplicates, revert. [Here](<https://github.com/safe-global/safe-smart-account/blob/main/contracts/Safe.sol#L312>) is an example of safe using this technique.
