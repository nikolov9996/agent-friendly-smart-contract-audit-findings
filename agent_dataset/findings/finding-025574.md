---
id: 25574
severity: "Crit/High"
---

# Draw auction rewards likely exceed the available rewards, resulting in overpaying rewards or running into an InsufficientReserve error

## Description



## Proof of Concept

## Vulnerability Detail

The `finishDraw` function calculates the rewards for starting and finishing a draw and distributes them to the respective participants. The total rewards (`availableRewards`) are based on the available prize pool reserve ([upper capped by `maxRewards`](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-draw-manager/src/DrawManager.sol#L507>)). Those rewards are then split into the start draw rewards and the finish draw rewards. Internally, the portion each participant receives is denominated in fractions ([0.00, 1.00]). No more than `availableRewards` (i.e., the upper cap or the total available prize pool reserve)can be distributed.

However, it is very likely that the sum of all fractions exceeds `1.0`, which would result in utilizing more rewards than `availableRewards`. Consequently, if the reserve has been larger than the `maxRewards` upper cap, more rewards would be paid out than `availableRewards`. Or, if the reserve has been smaller than `maxRewards`, which means the entire reserve is supposed to get used for rewards, using more than `1.0 * availableRewards` would [result in an `InsufficientReserve` error](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-prize-pool/src/PrizePool.sol#L439>).

Basically, in the former case, rewards are overpaid, and in the latter case, the draw can not be awarded due to the `InsufficientReserve` error.

The following test case demonstrates this issue by having two `startDraw` calls, both of which are supposed to receive `~0.1e18` rewards, which would already exceed the `0.1e18` available reserve. Please note that due to mocking the calls to the prize pool, the actual `InsufficientReserve` error is not triggered. However, by inspecting the emitted events, it can be seen that the rewards are overpaid.

```solidity
function test_finishDraw_multipleStarts_with_exceeding_reserve() public {
    vm.warp(1 days + auctionDuration);

    mockReserve(.1e18, 0);

    // 1st start draw
    mockRng(99, 0x1234);
    uint firstStartReward = 99999999999999999; // ~0.1e18
    vm.expectEmit(true, true, true, true);
    emit DrawStarted(address(this), alice, 1, auctionDuration, firstStartReward, 99, 1);
    drawManager.startDraw(alice, 99);

    // RNG fails
    mockRngFailure(99, true);

    // 2nd start draw
    vm.warp(1 days + auctionDuration + auctionDuration);
    vm.roll(block.number + 1);
    mockRng(100, 0x1234);
    uint secondStartReward = 99999999999999999; // ~0.1e18 - Would already exceed the available reserve of 0.1e18
    vm.expectEmit(true, true, true, true);
    emit DrawStarted(address(this), bob, 1, auctionDuration, secondStartReward, 100, 2);
    drawManager.startDraw(bob, 100);

    mockFinishDraw(0x1234);
    vm.warp(1 days + auctionDuration*3);
    uint finishReward = 99999999999999999; // ~0.1e18
    mockAllocateRewardFromReserve(alice, firstStartReward);
    mockAllocateRewardFromReserve(bob, secondStartReward);
    mockAllocateRewardFromReserve(bob, finishReward);
    mockReserveContribution(.1e18);
    assertEq(drawManager.finishDrawReward(), finishReward, "finish draw reward matches");
    drawManager.finishDraw(bob);
}
```

Please copy and paste the above test case into the `pt-v5-draw-manager/test/DrawManager.t.sol` file and run it with `forge test -vv --match-test "test_finishDraw_multipleStarts_with_exceeding_reserve"`.

## Impact

Either rewards for `startDraw` and `finishDraw` are overpaid, or the draw can not be awarded.

## Code Snippet

[DrawManager.finishDraw#L314-L352](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/main/pt-v5-draw-manager/src/DrawManager.sol#L314-L352>)

```solidity
314: function finishDraw(address _rewardRecipient) external returns (uint24) {
...    // [...]
333:   uint256 availableRewards = _computeAvailableRewards();
334:   (uint256[] memory startDrawRewards, UD2x18[] memory startDrawFractions) = _computeStartDrawRewards(
335:     prizePool.drawClosesAt(startDrawAuction.drawId),
336:     availableRewards
337:   );
338:   (uint256 _finishDrawReward, UD2x18 finishFraction) = _computeFinishDrawReward(
339:     startDrawAuction.closedAt,
340:     block.timestamp,
341:     availableRewards
342:   );
343:   uint256 randomNumber = rng.randomNumber(startDrawAuction.rngRequestId);
344:   uint24 drawId = prizePool.awardDraw(randomNumber);
345:
346:   lastStartDrawFraction = startDrawFractions[startDrawFractions.length - 1];
347:   lastFinishDrawFraction = finishFraction;
348:
349:   for (uint256 i = 0; i < _startDrawAuctions.length; i++) {
350:     _reward(_startDrawAuctions[i].recipient, startDrawRewards[i]);
351:   }
352:   _reward(_rewardRecipient, _finishDrawReward);
```

## Recommendation

Consider ensuring that the sum of all fractions does not exceed `1.0` to prevent overpaying rewards or running into an `InsufficientReserve` error.
