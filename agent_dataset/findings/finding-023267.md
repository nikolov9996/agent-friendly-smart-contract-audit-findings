---
id: 23267
severity: "Medium"
---

# User's might be able to claim their prizes even

## Description

User's might be able to claim their prizes even after shutdown due to lastObservationAt and draw period difference. There is no shutdown check kept on the claimPrize function. Hence user's can claim their prizes even after the pool has been shutdown if the draw has not been finalized.

```solidity
function claimPrize(
    address _winner,
    uint8 _tier,
    uint32 _prizeIndex,
    address _prizeRecipient,
    uint96 _claimReward,
    address _claimRewardRecipient
) external returns (uint256) {
    /// @dev Claims cannot occur after a draw has been finalized (1 period after a draw closes). This prevents
    /// the reserve from changing while the following draw is being awarded.
    uint24 lastAwardedDrawId_ = _lastAwardedDrawId;
    if (isDrawFinalized(lastAwardedDrawId_)) {
        revert ClaimPeriodExpired();
    }
```

The remaining balance after a shutdown is supposed to be allocated to user's based on their (vault prize contribution + twab contribution) via the withdrawShutdownBalance and is not supposed to be based on a random number ie. via claimPrize.

```solidity
function withdrawShutdownBalance(address _vault, address _recipient) external
returns (uint256) {
    if (!isShutdown()) {
        revert PrizePoolNotShutdown();
    }
```

In case the draw period is different from the TWAB's period length, it is not necessary that the shutdown due to the lastObservationAt occurs at the end of a draw. In such a case, it will allow user's who are winners of the draw to claim their prizes and also withdraw their share of the shutdown balance hence stealing funds from others. User's can double claim assets when vault shutdowns eventually.

## Proof of Concept

```
diff --git a/pt-v5-prize-pool/test/PrizePool.t.sol b/pt-v5-prize-pool/test/PrizePool.t.sol
index 99fe6b5..5ce7ad6 100644
--- a/pt-v5-prize-pool/test/PrizePool.t.sol
+++ b/pt-v5-prize-pool/test/PrizePool.t.sol
@@ -75,6 +75,7 @@ contract PrizePoolTest is Test {
    uint256 RESERVE_SHARES = 10;
    uint24 grandPrizePeriodDraws = 365;
+
    uint periodLength;
    uint48 drawPeriodSeconds = 1 days;
    uint24 drawTimeout; // = grandPrizePeriodDraws * drawPeriodSeconds; // 1000 days;
@@ -112,27 +113,26 @@ contract PrizePoolTest is Test {
    ConstructorParams params;
-
    function setUp() public {
-
        drawTimeout = 30; //grandPrizePeriodDraws;
-
        vm.warp(startTimestamp);
+
    function setUp() public {
+
        // at end drawPeriod == 2 day, and period length in twab = 1 day
+
        periodLength = 1 days;
+
        drawPeriodSeconds = 2 days;
+
+
        // the last draw should be ending at lastObservation timestamp + 1 day
+
        startTimestamp = 1000 days;
+
        firstDrawOpensAt =
            uint48((type(uint32).max / periodLength ) % 2 == 0 ?
            startTimestamp + 1 days : startTimestamp + 2 days);
+
+
+
+
        drawTimeout = 25854; // to avoid shutdown by drawTimeout when warping
+
+
        vm.warp(startTimestamp + 1);
        prizeToken = new ERC20Mintable("PoolTogether POOL token", "POOL");
-
        twabController = new TwabController(uint32(drawPeriodSeconds), uint32(startTimestamp - 1 days));
+
        twabController = new TwabController(uint32(periodLength), uint32(startTimestamp));
-
        firstDrawOpensAt = uint48(startTimestamp + 1 days); // set draw start 1 day into future
-
        vm.mockCall(
            address(twabController),
            abi.encodeCall(twabController.PERIOD_OFFSET, ()),
            abi.encode(firstDrawOpensAt)
        );
-
        vm.mockCall(
            address(twabController),
            abi.encodeCall(twabController.PERIOD_LENGTH, ()),
            abi.encode(drawPeriodSeconds)
        );
-
        drawManager = address(this);
        vault = address(this);
        vault2 = address(0x1234);
@@ -142,7 +142,7 @@ contract PrizePoolTest is Test {
        twabController,
        drawManager,
        tierLiquidityUtilizationRate,
-
        drawPeriodSeconds,
+
        uint48(drawPeriodSeconds),
        firstDrawOpensAt,
        grandPrizePeriodDraws,
        initialNumberOfTiers, // minimum number of tiers
@@ -155,6 +155,51 @@ contract PrizePoolTest is Test {
        prizePool = newPrizePool();
    }
+
    function testHash_CanClaimPrizeAfterShutdown() public {
+
        uint secondLastDrawStart = startTimestamp + (type(uint32).max / periodLength ) * periodLength - 3 days;
+
+
        vm.warp(secondLastDrawStart + 1);
+
        address user1 = address(100);
+
        //address user2 = address(200);
+
+
        // mint tokens to the user in twab
+
        twabController.mint(user1, 10e18);
+
        //twabController.mint(user2, 5e18);
+
+
        // contribute prize tokens to the vault
+
        prizeToken.mint(address(prizePool),100e18);
+
        prizePool.contributePrizeTokens(address(this),100e18);
+
+
        // move to the next draw and award this one
+
        vm.warp(secondLastDrawStart + drawPeriodSeconds + 1);
+
        prizePool.awardDraw(100);
+
        uint drawId = prizePool.getOpenDrawId();
+
+
        //currently not shutdown. but shutdown will occur in the middle of this draw allowing both prize claiming and the shutdown withdrawal
+
        uint shutdownTimestamp = prizePool.shutdownAt();
+
        assert(shutdownTimestamp == secondLastDrawStart + drawPeriodSeconds + periodLength);
+
+
        vm.warp(shutdownTimestamp);
+
+
        // call to store the shutdown data before the prize is claimed
+
        prizePool.shutdownBalanceOf(address(this),user1);
+
+
        /**
         * address _winner,
         * uint8 _tier,
         * uint32 _prizeIndex,
         * address _prizeRecipient,
         * uint96 _claimReward,
         * address _claimRewardRecipient
         */
+
        prizePool.claimPrize(user1,1,0,user1,0,address(0));
+
+
        // no withdrawing shutdown balance will revert due to the amount being withdrawn earlier via the claimPrize function
+
        vm.prank(user1);
+
        vm.expectRevert();
+
        prizePool.withdrawShutdownBalance(address(this),user1);
+
    }
+
    function testConstructor() public {
        assertEq(prizePool.firstDrawOpensAt(), firstDrawOpensAt);
        assertEq(prizePool.drawPeriodSeconds(), drawPeriodSeconds);
```

## Recommendation

Add a notShutdown modifier to the claimPrize function

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the prize‑claiming function of the prize pool contract, which does not verify whether the pool has been shut down before allowing a winner to claim a prize. The contract tracks two independent time‑bases: the draw period, which determines when a draw opens and closes, and the TWAB (time‑weighted average balance) period, which determines when the pool may be shut down based on the last observation timestamp. When these periods differ, the shutdown can occur in the middle of an active draw – specifically after the last observation timestamp but before the draw is marked as finalized. Because the claimPrize function only checks that the draw has not been finalized (using isDrawFinalized) and lacks a check that the pool is not in shutdown, a winner can invoke claimPrize after the shutdown timestamp. The claim transfers the prize amount to the winner, and the same winner can subsequently call withdrawShutdownBalance to retrieve their share of the remaining pool balance, which should have been allocated only once. This results in a double‑claim scenario where the same assets are withdrawn twice, effectively stealing funds from other participants. From a user’s perspective the symptom is that a winner can still receive a prize after the pool is announced as shut down, and then the pool balance for other users appears reduced or even zero, contrary to the expectation that no further claims are possible after shutdown. The issue was discovered during a formal audit when a test case simulated a mismatch between draw and TWAB periods and observed that claimPrize succeeded after the shutdown timestamp, followed by a successful shutdown balance withdrawal that reverted only because the funds had already been taken. The bug is subtle because the shutdown condition is extremely rare – it only occurs when the TWAB controller reaches its maximum uint32 timestamp (approximately 82 years) and when the draw period is not a multiple of the TWAB period – making it easy to overlook in normal testing. The root cause is the missing shutdown guard in claimPrize; the contract should enforce that no prize can be claimed after a shutdown, for example by adding a notShutdown modifier or by aligning the draw and TWAB periods so that shutdown can only happen after a draw is finalized. Conceptually, this is a classic case of improper state validation leading to double‑spending of assets, violating the accounting assumptions that each prize and each shutdown share can be withdrawn exactly once.
