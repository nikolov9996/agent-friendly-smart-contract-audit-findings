---
id: 25070
severity: "Medium"
---

# Unconditional lastUpdated advance in RangePool.sync leads to loss of streamed BMX when pool liquidity == 0

## Description



## Proof of Concept

1. Place the test in the `GaugeStream.t.sol` test file.
2. Run the test using this ` forge test --mt testLostStreamingWhenZeroLiquidity -vvvv`

```JavaScript
 /// @notice Demonstrates that if a pool has zero liquidity when the gauge
    ///         sync runs, the per-day bucket amounts are not applied to the
    ///         pool accumulator (they become effectively unallocated to any
    ///         position). This reproduces the "lost streaming when
    ///         liquidity==0" behaviour: tokens remain in the gauge balance
    ///         but positions can't claim them.
    function testLostStreamingWhenZeroLiquidity() public {
        // Precondition: setUp has funded the gauge and added a day-bucket.
        uint256 bucket = 1000 ether;

        // Ensure initial gauge balance contains the bucket
        assertGe(bmx.balanceOf(address(gauge)), bucket);

        // 1) Remove the only tracked liquidity so pool active liquidity == 0
        positionManager.unsubscribe(wideTokenId);

        // Confirm pool has zero active liquidity now via gauge view
        (,, uint128 activeLiq) = gauge.getPoolData(pid);
        assertEq(activeLiq, 0, "pool liquidity should be zero");

        // 2) Advance to the streaming day (N+2) so the gauge will try to credit
        uint256 dayEnd = TimeLibrary.dayNext(block.timestamp);
        vm.warp(dayEnd + 1 days);

        // Sanity: streamRate should be non-zero because the day-bucket exists
        assertGt(gauge.streamRate(pid), 0, "streamRate should be active for the day");

        // 3) Trigger pool sync while liquidity == 0. Because RangePool.sync
        //    updates lastUpdated before accumulating, the amounts for the
        //    elapsed window are not applied when liquidity==0.
        vm.prank(address(hook));
        gauge.pokePool(key);

        // 4) Re-add liquidity (mint and subscribe a fresh position after the
        //    missed window). This new position cannot recover the previously
        //    scheduled streaming for the earlier window.
        uint256 tokenIdNew;
        (tokenIdNew,) = EasyPosm.mint(
            positionManager,
            key,
            -60000,
            60000,
            1e21,
            type(uint256).max,
            type(uint256).max,
            address(this),
            block.timestamp + 1 hours,
            bytes("")
        );
        positionManager.subscribe(tokenIdNew, address(adapter), bytes(""));

        // 5) Sync now that liquidity > 0. Only amounts since the previous
        //    lastUpdated will be applied — the bucket that streamed during
        //    The earlier zero-liquidity window is not credited to positions.
        vm.prank(address(hook));
        gauge.pokePool(key);

        // 6) Claim for owner: should receive zero (or very small) because the
        // Earlier, the streaming window was missed when liquidity was 0.
        PoolId[] memory arr = new PoolId[](1);
        arr[0] = pid;
        uint256 balBefore = bmx.balanceOf(address(this));
        gauge.claimAllForOwner(arr, address(this));
        uint256 claimed = bmx.balanceOf(address(this)) - balBefore;

        // The test demonstrates the bug: the bucket is still sitting in the
        // gauge contract balance but positions received nothing for the
        // streaming window that occurred while liquidity was zero.
        assertEq(claimed, 0, "expected no rewards allocated to position");
        assertGe(bmx.balanceOf(address(gauge)), bucket, "gauge should still hold the bucket funds");
    }
```

## Impact

- Funds meant for distribution (BMX) are retained in the gauge balance but never credited to any pool accumulator for claim by LP positions.
- LPs present after liquidity returns cannot claim past streaming amounts; protocol revenue intended for LPs can be effectively sidelined.
- Denial of reward for LPs; accounting mismatch between gauge token balance and claimable amounts.
- This is not an immediate theft but a correctness/availability failure with lasting distribution impact.

## Recommendation

Do not advance lastUpdated and therefore do not consume the elapsed-window amounts. when `self.liquidity == 0`. Return early so the pending per-day amounts remain available and are applied once liquidity appears.

Apply changes in the `RangePool.sol::sync`

```diff
@@
-        // 1. Update lastUpdated and credit per-token amounts
-        self.lastUpdated = uint64(block.timestamp);
-
-        if (self.liquidity > 0) {
-            uint256 len = tokens.length;
-            for (uint256 i; i < len; ++i) {
-                _accumulateToken(self, tokens[i], perTokenAmounts[i]);
-            }
-        }
+        // If no active liquidity, do not advance lastUpdated or consume amounts.
+        // Preserve the time window so amounts are processed later when liquidity exists.
+        if (self.liquidity == 0) {
+            // Adjust price movement if needed, but keep lastUpdated unchanged.
+            if (activeTick != self.tick) {
+                self.adjustToTick(tickSpacing, activeTick, tokens);
+            }
+            return;
+        }
+
+        // 1. Update lastUpdated and credit per-token amounts
+        self.lastUpdated = uint64(block.timestamp);
+
+        uint256 len = tokens.length;
+        for (uint256 i; i < len; ++i) {
+            _accumulateToken(self, tokens[i], perTokenAmounts[i]);
+        }
```
