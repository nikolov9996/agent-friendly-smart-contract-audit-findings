---
id: 25419
severity: "Low/Info"
---

# RedeemQueue::findOffsetIndex() does not check the last index

## Description

RedeemQueue::findOffsetIndex() performs binary search but does not check the last index when doing so, as it assigns uint256 r = len_ - 1;. For example, consider l == 0, len == 3, so r == 2 and [there](<https://docs.soliditylang.org/en/latest/style-guide.html>) are requests 0, 1 and 2.

First iteration, m == 0 + (2 - 0) / 2 == 1. isReserved() returns true l == m + 1 == 1 + 1 == 2 and it leaves the while loop as l == r == 2. Thus, the last index is not checked (m == 2).

## Proof of Concept

No PoC provided.

## Recommendation

uint256 r = len_; would correctly check index 2 and assign l to 3 in this case. Additionally, consider exposing this function in the BasicVault as it currently is not.
