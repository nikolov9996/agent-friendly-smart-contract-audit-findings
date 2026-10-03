---
id: 25486
severity: "Low/Info"
---

# PositionManager:_reversePosition() calculates the notional to reverse but could just use the exchangedQuote

## Description

[PositionManager:_reversePosition()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/clearinghouse-libs/PositionManager.sol#L1027>) reduces the notional by the amount required to close the previous position, fetching the value using the [getters](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/clearinghouse-libs/PositionManager.sol#L1021-L1025>) before.

However, it could use closeResponse.exchangedQuote() instead, which does the same calculations.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
