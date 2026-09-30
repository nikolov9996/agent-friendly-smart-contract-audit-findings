---
id: 18999
severity: "High"
---

# Increasing reserves breaks PrizePool accounting

## Description

When anyone calls the `increaseReserve` method in `PrizePool.sol` the accounted balance in the prize pool isn’t properly updated. This allows a vault to effectively steal the prize token contribution and this contribution gets distributed during draws; effectively double counting the initial injection into the reserves. The actual prize token balance of the prize pool will be below the accounted balance of the prize pool as time goes on.

## Proof of Concept

As mentioned in the audit README:

"the balance of prize tokens held by the contract must always be equal to the sum of the available tier liquidity and the reserve. When contributing liquidity, the prize pool will temporarily hold a balance greater than the accounted balance, but otherwise the two should match".

Unfortunately, this is broken when anyone contributes directly to the reserve by calling `increaseReserve`.

In the normal audit flow, the reserve is increased when a draw is closed by the draw manager. During calls to `closeDraw`, the next draw is started with a given number of tiers and the contributions for the round are calculated and split across the tiers and the reserve:
    
    _nextDraw(_nextNumberOfTiers, uint96(_contributionsForDraw(lastClosedDrawId + 1)));

Under the hood, this calls `_computeNewDistributions` which calculates the amount to increase the reserves, based on the number of reserve shares and the new prize token liquidity being contributed in this round. During this flow, the actual balance of reward tokens held in the prize pool are equal to the accounted balance.

The break in accounting occurs when calling `increaseReserve`:
    
```solidity
function increaseReserve(uint104 _amount) external {
  _reserve += _amount;
  prizeToken.safeTransferFrom(msg.sender, address(this), _amount);
  emit IncreaseReserve(msg.sender, _amount);
}
```

As you can see, the prize tokens are transferred into the pool and the reserve increased. But the accounted balance is unchanged:
    
```solidity
function _accountedBalance() internal view returns (uint256) {
  Observation memory obs = DrawAccumulatorLib.newestObservation(totalAccumulator);
  return (obs.available + obs.disbursed) - _totalWithdrawn;
}
```

Because the accounted balance is unchanged, any vault can now call `contributePrizeTokens` to effectively steal the funds meant for the reserve:
    
```solidity
function contributePrizeTokens(address _prizeVault, uint256 _amount) external returns (uint256) {
  uint256 _deltaBalance = prizeToken.balanceOf(address(this)) - _accountedBalance();
```

This increases the relevant vault accumulator and the total accumulator; thereby, effectively double counting the same prize tokens, since we've already increased `_reserve`.

## Recommendation

The accounted balance of the prize pool should be updated when `increaseReserve` is called. I think the easiest way of achieving this is having a tracker for "reserve injections":
    
```diff
diff --git a/src/PrizePool.sol b/src/PrizePool.sol
index a42a27e..3c14476 100644
--- a/src/PrizePool.sol
+++ b/src/PrizePool.sol
@@ -233,6 +233,9 @@ contract PrizePool is TieredLiquidityDistributor {
   /// @notice The total amount of prize tokens that have been claimed for all time.
   uint256 internal _totalWithdrawn;
 
+  /// @notice The total amount of reserve injections that have been performed for all time.
+  uint256 internal _reserveInjections;
+
   /// @notice The winner random number for the last closed draw.
   uint256 internal _winningRandomNumber;
 
@@ -497,6 +500,7 @@ contract PrizePool is TieredLiquidityDistributor {
   /// @param _amount The amount of tokens to increase the reserve by
   function increaseReserve(uint104 _amount) external {
     _reserve += _amount;
+    _reserveInjections += _amount;
     prizeToken.safeTransferFrom(msg.sender, address(this), _amount);
     emit IncreaseReserve(msg.sender, _amount);
   }
@@ -742,7 +746,7 @@ contract PrizePool is TieredLiquidityDistributor {
   /// @return The balance of tokens that have been accounted for
   function _accountedBalance() internal view returns (uint256) {
     Observation memory obs = DrawAccumulatorLib.newestObservation(totalAccumulator);
-    return (obs.available + obs.disbursed) - _totalWithdrawn;
+    return (obs.available + obs.disbursed) - _totalWithdrawn + _reserveInjections;
   }
 
   /// @notice Returns the start time of the draw for the next successful closeDraw
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mismatch in the prize pool contract that occurs when the reserve is increased through the public increaseReserve function. The root cause is that the internal accounting routine that calculates the pool's accounted balance does not incorporate reserve injections performed via increaseReserve, so the variable that tracks the total accounted tokens remains unchanged while the actual token balance of the contract grows. An attacker can exploit this by first calling increaseReserve to transfer prize tokens into the contract and increase the reserve, and then invoking the contributePrizeTokens function (or any similar path that uses the delta between the real token balance and the accounted balance). Because the accounted balance does not reflect the newly injected reserve, the delta includes the attacker’s own contribution, allowing the attacker’s vault to claim those tokens as if they were newly earned prize liquidity. The impact is that the prize pool’s real token holdings become lower than the amount the protocol believes it has, leading to reduced or missing prize payouts for users, potential loss of funds for participants, and a breach of the protocol’s financial guarantees. This condition occurs whenever any address is permitted to call increaseReserve – a permissionless entry point – and later calls a function that distributes the perceived excess balance. The affected parties include the prize pool contract itself, any vaults that can call contributePrizeTokens, and ultimately the end‑users who expect their prizes to be funded correctly. The issue was discovered during a formal audit when the auditors checked the invariant that the contract’s token balance must equal the sum of available tier liquidity and the reserve; the invariant failed after a manual reserve injection. The bug is subtle because the contract’s balance appears correct during normal draw closures, and only diverges after an external reserve increase, making the discrepancy easy to miss in routine testing. To remediate, the contract should update its accounted balance whenever the reserve is increased, for example by tracking total reserve injections and adding that amount to the accounted balance calculation, thereby preserving the accounting invariant and preventing double counting of the same tokens. This fix restores the logical accounting model where every token held by the contract is reflected in the internal accounting state, ensuring that prize distribution matches the actual token pool.
