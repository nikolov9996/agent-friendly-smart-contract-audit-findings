---
id: 19193
severity: "High"
---

# Too many rewards are distributed when a draw is closed

## Description

A relayer completes a prize pool draw by calling `rngComplete` in `RngRelayAuction.sol`. This method closes the prize pool draw with the relayed random number and distributes the rewards to the RNG auction recipient and the RNG relay auction recipient. These rewards are calculated based on a fraction of the prize pool reserve rather than an actual value.

However, the current reward calculation mistakenly includes an extra `reserveForOpenDraw` amount just after the draw has been closed. Therefore the fraction over which the rewards are being calculated includes tokens that have not been added to the reserve and will actually only be added to the reserve when the next draw is finalised. As a result, the reward recipients are rewarded too many tokens.

## Proof of Concept

Before deciding whether or not to relay an auction result, a bot can call `computeRewards` to calculate how many rewards they’ll be getting based on the size of the reserve, the state of the auction and the reward fraction of the RNG auction recipient:
    
```solidity
function computeRewards(AuctionResult[] calldata __auctionResults) external returns (uint256[] memory) {
    uint256 totalReserve = prizePool.reserve() + prizePool.reserveForOpenDraw();
    return _computeRewards(__auctionResults, totalReserve);
}
```

Here, the total reserve is calculated as the sum of the current reserve and and amount of new tokens that will be added to the reserve once the currently open draw is closed. This method is correct and correctly calculates how many rewards should be distributed when a draw is closed.

A bot can choose to close the draw by calling `rngComplete` (via a relayer), at which point the rewards are calculated and distributed. Below is the interesting part of this method:
    
```solidity
uint32 drawId = prizePool.closeDraw(_randomNumber);

uint256 futureReserve = prizePool.reserve() + prizePool.reserveForOpenDraw();
uint256[] memory _rewards = RewardLib.rewards(auctionResults, futureReserve);
```

As you can see, the draw is first closed and then the future reserve is used to calculate the rewards that should be distributed. However, when `closeDraw` is called on the pool, the `reserveForOpenDraw` for the previously open draw is added to the existing reserves. So `reserve()` is now equal to the `totalReserve` value in the earlier call to `computeRewards`. By including `reserveForOpenDraw()` when computing the actual reward to be distributed we’ve accidentally counted the tokens that are only going to be added in when the next draw is closed. So now the rewards distribution calculation includes the pending reserves for 2 draws rather than 1.

## Recommendation

When distributing rewards in the call to `rngComplete`, the rewards should not be calculated with the new value of `reserveForOpenDraw` because the previous `reserveForOpenDraw` value has already been added to the reserves when `closeDraw` is called on the prize pool. Below is a suggested diff:
    
```diff
diff --git a/src/RngRelayAuction.sol b/src/RngRelayAuction.sol
index 8085169..cf3c210 100644
--- a/src/RngRelayAuction.sol
+++ b/src/RngRelayAuction.sol
@@ -153,8 +153,8 @@ contract RngRelayAuction is IRngAuctionRelayListener, IAuction {
 
     uint32 drawId = prizePool.closeDraw(_randomNumber);
 
-    uint256 futureReserve = prizePool.reserve() + prizePool.reserveForOpenDraw();
-    uint256[] memory _rewards = RewardLib.rewards(auctionResults, futureReserve);
+    uint256 reserve = prizePool.reserve();
+    uint256[] memory _rewards = RewardLib.rewards(auctionResults, reserve);
 
     emit RngSequenceCompleted(
       _sequenceId,
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an over‑allocation of rewards that occurs when a prize pool draw is closed through the rngComplete function. The contract closes the draw, which automatically adds the amount stored in reserveForOpenDraw to the pool's main reserve, and then mistakenly calculates the reward amounts using a futureReserve value that adds reserveForOpenDraw a second time. This double‑counting of the pending reserve means the reward fraction is applied to tokens that have not yet been minted, resulting in reward recipients receiving more tokens than the protocol’s accounting rules allow. The root cause is a logical error in the reward calculation order: the code uses prizePool.reserve() + prizePool.reserveForOpenDraw() after closeDraw has already incorporated reserveForOpenDraw into reserve(), effectively counting the same tokens twice. An attacker can exploit this by first calling computeRewards to see the inflated reward amount, then triggering rngComplete (or a relayer calling it) to close the draw and claim the excess tokens. The impact is that the protocol distributes extra tokens, draining the prize pool’s reserves faster than intended and breaking the economic guarantees of the lottery. This condition occurs every time a draw is closed while the reward calculation uses the futureReserve expression, affecting any participant who receives rewards, as well as token holders who rely on the pool’s integrity. The issue was discovered during a formal audit by Code4rena, and it can be subtle because the reward numbers appear plausible and the over‑payment may be small per draw, making it hard to notice without detailed accounting checks. From a user perspective the symptoms are unexpectedly large reward payouts, a rapid decrease in the pool’s visible balance, or draws that seem to give out more tokens than the advertised prize structure. The bug belongs to the class of accounting miscalculations where pending funds are double‑counted, leading to reward over‑distribution. To fix the issue the reward calculation should use only the current reserve after closeDraw, removing the addition of reserveForOpenDraw, so that RewardLib receives the correct reserve amount and the reward fraction is applied to the true available token pool.
