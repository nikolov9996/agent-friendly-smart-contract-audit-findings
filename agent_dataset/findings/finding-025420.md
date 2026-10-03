---
id: 25420
severity: "Low/Info"
---

# RedeemQueue could be optimized

## Description

The current RedeemQueue implementation goes through requests and marks them as resolved one by one. This is expensive and a much better solution is keeping track of the last index that was resolved, and if the request index is smaller than the last resolved, it means it was resolved (indices are sequential).

[Here](<https://github.com/lidofinance/lido-dao/blob/master/contracts/0.8.9/WithdrawalQueueBase.sol#L332>) is the function that settles redeem requests. It gets the correct index to redeem until to by perform binary search, but can also pass it as argument (so the search is performed off chain).

It's also not required to store request.amount as it can be calculated by fetching the last request and subtracting from the current cumulative amount.

## Proof of Concept

No PoC provided.

## Recommendation

It would be much cheaper to redeem batches at once, so a similar method to Lido's could be implemented.
