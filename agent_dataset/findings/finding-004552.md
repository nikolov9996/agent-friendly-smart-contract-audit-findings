---
id: 4552
severity: "High"
---

# Permanent Locking of User Funds in the Stability Pool Submitted by etherSky, also found by santipu, T1MOH and pkqs90

## Description

```solidity
Assume the sunsetted collateral is assigned index 1.
Let the current epoch be E and the current scale be S. Users have already earned gains from this collateral, meaning depositSums[1] is greater than 0 for these users. After 180 days, the sunsetted collateral is replaced with a new one.
• StabilityPool.sol#L223:
function _overwriteCollateral(IERC20 _newCollateral, uint256 idx) internal {
    for (uint128 i; i <= externalLoopEnd; ) {
        for (uint128 j; j <= internalLoopEnd; ) {
            epochToScaleToSums[i][j][idx] = 0;
            unchecked {
                ++j;
            }
        }
        unchecked {
            ++i;
        }
    }
    collateralTokens[idx] = _newCollateral;
}
In line 223, epochToScaleToSums[E][S][1] is reset to 0. Assume there is a user A with depositSums[1] = 10,000.
Through an offset, the new collateral generates some gains, causing epochToScaleToSums[E][S][1] to increase to 200 or a similar value (still less than 10,000).
At this point, all operations—such as provideToSP, withdrawFromSP, and _claimReward, which invoke the _accrueDepositorCollateralGain function—would fail and revert.
• StabilityPool.sol#L657:
function _accrueDepositorCollateralGain(address _depositor) private returns (bool hasGains) {
    uint80[MAX_COLLATERAL_COUNT] storage depositorGains = collateralGainsByDepositor[_depositor];
    uint256 collaterals = collateralTokens.length;
    uint256 initialDeposit = accountDeposits[_depositor].amount;
    if (initialDeposit != 0) {
        uint128 epochSnapshot = depositSnapshots[_depositor].epoch;
        uint128 scaleSnapshot = depositSnapshots[_depositor].scale;
        uint256 P_Snapshot = depositSnapshots[_depositor].P;
        uint256[MAX_COLLATERAL_COUNT] storage sumS = epochToScaleToSums[epochSnapshot][scaleSnapshot];
        uint256[MAX_COLLATERAL_COUNT] storage nextSumS = epochToScaleToSums[epochSnapshot][scaleSnapshot + 1];
        uint256[MAX_COLLATERAL_COUNT] storage depSums = depositSums[_depositor];
        for (uint256 i; i < collaterals; i++) {
            if (sumS[i] == 0) continue; // Collateral was overwritten or not gains
            hasGains = true;
            uint256 firstPortion = sumS[i] - depSums[i];
            uint256 secondPortion = nextSumS[i] / BIMA_SCALE_FACTOR;
            depositorGains[i] += SafeCast.toUint80(
                (initialDeposit * (firstPortion + secondPortion)) / P_Snapshot / BIMA_DECIMAL_PRECISION
            );
        }
    }
}
An underflow occurs in line 657.
As a result, user A's funds remain locked until epochToScaleToSums[E][S][1] exceeds depositSums[1].
This process cannot be manually controlled, as all values are updated automatically through offsets.
Moreover, if the scale or epoch increases before this condition is met, user A will lose all their funds.
```

Impact Explanation:
The impact is that users are unable to deposit or withdraw their underlying tokens when they want. In some cases, they would lose all their funds, including any rewards, as there is no mechanism to increase epochToScaleToSums for those old epochs and scales.

## Proof of Concept

```solidity
Please add the following test file to the test/foundry directory.
// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;
import {TestSetup, IIncentiveVoting, SafeCast} from "./TestSetup.sol";
import {StakedBTC} from "../../contracts/mock/StakedBTC.sol";
import {Factory, IFactory} from "../../contracts/core/Factory.sol";
import {PriceFeed} from "../../contracts/core/PriceFeed.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "forge-std/console2.sol";
contract TestStabilityPoolTest2 is TestSetup {
    function setUp() public virtual override {
        super.setUp();
        /**
        only 1 collateral token exists due to base setup.
        */
        assertEq(stabilityPool.getNumCollateralTokens(), 1);
        /**
        The collateral token is stakedBTC.
        */
        assertEq(address(stabilityPool.collateralTokens(0)), address(stakedBTC));
    }
    function test_stabilityPool_sunset_withdraw() external {
        uint256 depositAmount = 20e18;
        vm.prank(address(borrowerOps));
        debtToken.mint(users.user1, depositAmount);
        assertEq(debtToken.balanceOf(users.user1), depositAmount);
        vm.prank(users.user1);
        /**
        User1 provides debtTokens to the Stability Pool.
        */
        stabilityPool.provideToSP(depositAmount);
        vm.prank(address(liquidationMgr));
        /**
        For testing purposes:
        - A 5e18 debt loss occurs.
        - A 5e18 collateral gain is applied.
        */
        stabilityPool.offset(stakedBTC, 5e18, 5e18);
        vm.prank(users.user1);
        /**
        To update collateralGainsByDepositor, User1 calls the claimReward function.
        */
        stabilityPool.claimReward(users.user1);
        vm.prank(users.owner);
        /**
        The stakedBTC collateral is sunsetted.
        */
        stabilityPool.startCollateralSunset(stakedBTC);
        /**
        After 200 days, the stakedBTC can be replaced with new collateral.
        */
        vm.warp(block.timestamp + 200 days);
        console2.log(stabilityPool.depositSums(users.user1, 0), stabilityPool.epochToScaleToSums(0, 0, 0));
        vm.prank(users.owner);
        StakedBTC newCollateral = new StakedBTC();
        vm.prank(address(factory));
        /**
        A new collateral token is enabled. (Suppose this new collateral is much more valuable than stakedBTC.)
        */
        stabilityPool.enableCollateral(newCollateral);
        vm.prank(address(borrowerOps));
        debtToken.mint(users.user2, depositAmount);
        vm.prank(users.user2);
        /**
        User2 provides debtTokens to the Stability Pool.
        */
        stabilityPool.provideToSP(depositAmount);
        console2.log(stabilityPool.depositSums(users.user1, 0), stabilityPool.epochToScaleToSums(0, 0, 0));
        vm.prank(address(liquidationMgr));
        /**
        For testing purposes:
        - A 5e18 debt loss occurs.
        - A 1e18 collateral gain is applied.
        */
        stabilityPool.offset(newCollateral, 5e18, 1e18);
        console2.log(stabilityPool.depositSums(users.user1, 0), stabilityPool.epochToScaleToSums(0, 0, 0));
        /**
        0: normal mode
        1: withdraw test
        2: provide test
        3: claim rewards test
        */
        uint256 TEST_MODE = 0;
        if (TEST_MODE == 1) {
            vm.prank(users.user1);
            stabilityPool.withdrawFromSP(1e18);
        }
        if (TEST_MODE == 2) {
            vm.prank(address(borrowerOps));
            debtToken.mint(users.user1, depositAmount);
            assertEq(debtToken.balanceOf(users.user1), depositAmount);
            vm.prank(users.user1);
            stabilityPool.provideToSP(depositAmount);
        }
        if (TEST_MODE == 3) {
            uint256[] memory collateralIndexes = new uint256[](1);
            collateralIndexes[0] = 0;
            vm.prank(users.user1);
            stabilityPool.claimCollateralGains(users.user1, collateralIndexes);
        }
    }
}
In the test described above, we observed that depositing, withdrawing, and claiming rewards are reverted by changing TEST_MODE to 1, 2, or 3.
```

## Recommendation

```solidity
Track epochToScaleToSums and depositSums per token instead of per index.
- mapping(address depositor => uint256[MAX_COLLATERAL_COUNT] deposits) public depositSums;
+ mapping(address depositor => mapping(IERC20 => uint256)) public depositSums;
- mapping(uint128 epoch => mapping(uint128 scale => uint256[MAX_COLLATERAL_COUNT] sumS)) public epochToScaleToSums;
+ mapping(uint128 epoch => mapping(uint128 scale => mapping(IERC20 => uint256))) public epochToScaleToSums;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

Permanent locking of user funds occurs when the Stability Pool overwrites a sunsetted collateral token. The internal mapping epochToScaleToSums that tracks accrued collateral gains per epoch and scale is reset to zero for the old collateral index. When a user who deposited before the sunset later triggers any operation that reads this mapping—such as provideToSP, withdrawFromSP, or claimReward—the _accrueDepositorCollateralGain function reads a zero sumS entry and attempts to compute a gain using the user's deposit snapshot. Because the stored sumS value is smaller than the user's recorded depositSums, the subtraction sumS[i] - depSums[i] underflows, causing the transaction to revert. As a result, the user cannot withdraw their principal, cannot claim accrued rewards, and any further deposits also revert. The lock persists until epochToScaleToSums for the old epoch and scale grows larger than the user's deposit amount, which cannot happen because the protocol no longer updates those entries after the collateral has been replaced. If the epoch or scale advances before the condition is met, the user's entire balance is effectively lost. The issue was discovered during a formal audit and reproduced with a Foundry test that forced a collateral sunset, enabled a new token, and then attempted withdrawals, which all reverted. The bug is hard to notice because the contract does not emit a specific error; it simply reverts, and the UI may show no change in balance, leading users to think the transaction failed silently. The root cause is the use of a per‑index storage layout for epochToScaleToSums and depositSums, which does not preserve per‑token accounting when a collateral token is overwritten. The correct fix is to track these values per token address rather than by a numeric index, ensuring that old collateral entries are never cleared in a way that breaks the arithmetic for existing depositors. This class of bug is a state‑inconsistent accounting error that breaks the invariant that accrued gains must never be less than the user's recorded deposit, leading to permanent fund lock.
