---
id: 25573
severity: "Medium"
---

# DrawManager.canStartDraw does not consider retried RNG requests when determining if a new draw auction can be started

## Description



## Proof of Concept

## Vulnerability Detail

The `DrawManager.canStartDraw` function checks if the `startDraw` function can be called. However, the checks are not consistent with the `startDraw` function. Specifically, the check in line `289` to determine if the draw has expired is different than the auction duration check in the `startDraw` function in lines [`250-251`](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-draw-manager/src/DrawManager.sol#L250-L251>). The latter uses the last RNG request's `closedAt` timestamp to determine the elapsed **auction** time, to consider any retried failed RNG requests, while the former checks if the **draw** has expired, not considering retried RNG requests.

As a result, if for a given draw a RNG request has been retried, and thus the total elapsed time from the draw close until now (`block.timestamp`) might exceed the auction duration, off-chain actors calling the `canStartDraw` function might wrongly assume that the draw auction can not be started, even though such a call would succeed.

## Impact

As `canStartDraw` is also [called internally by the `startDrawReward` function](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-draw-manager/src/DrawManager.sol#L296-L298>) and both functions are likely to be used by off-chain actors to determine if a new draw auction an be started, this might lead to wrongly assuming that a new draw auction cannot be started, even though it should be possible. As a result, the current draw might not get awarded.

## Code Snippet

[DrawManager.canStartDraw()](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-draw-manager/src/DrawManager.sol#L289>)

```solidity
275: /// @notice Checks if the start draw can be called.
276: /// @return True if start draw can be called, false otherwise
277: function canStartDraw() public view returns (bool) {
278:   uint24 drawId = prizePool.getDrawIdToAward();
279:   uint48 drawClosesAt = prizePool.drawClosesAt(drawId);
280:   StartDrawAuction memory lastStartDrawAuction = getLastStartDrawAuction();
281:   return (
282:     (
283:       // if we're on a new draw
284:       drawId != lastStartDrawAuction.drawId ||
285:       // OR we're on the same draw, but the request has failed and we haven't retried too many times
286:       (rng.isRequestFailed(lastStartDrawAuction.rngRequestId) && _startDrawAuctions.length <= maxRetries)
287:     ) && // we haven't started it, or we have and the request has failed
288:     block.timestamp >= drawClosesAt && // the draw has closed
289: ❌  _computeElapsedTime(drawClosesAt, block.timestamp) <= auctionDuration // the draw hasn't expired
290:   );
291: }
```

## Recommendation

Consider using the last request's `closedAt` timestamp instead of `drawClosesAt` to determine if the auction has expired to consider failed RNG requests that have been retried by calling `startDraw` again.
