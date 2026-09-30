---
id: 4580
severity: "High"
---

# Relocking through MFDBase::claimBounty() leads to accounting error and causes funds loss Submitted by KlosMitSoss, also found by mussucal, 0x37 and aksoy

## Description

```solidity
function _afterStakeHook(uint256 _amount) internal override {
    IGauge gauge = getGauge();
    // Pull any rewards from the gauge
    if (gauge.earned(address(this)) > 0) {
        gauge.getReward(address(this));
    }
    // Stake in gauge
    IERC20(_getMFDBaseStorage().stakeToken).forceApprove(address(gauge), _amount);
    gauge.deposit(_amount, address(this)); // <<<
}

function _beforeWithdrawExpiredLocks(uint256 _amount) internal override {
    IGauge gauge = getGauge();
    // Pull any rewards from the gauge
    if (gauge.earned(address(this)) > 0) {
        gauge.getReward(address(this));
    }
    // Unstake from Gauge
    gauge.withdraw(_amount); // <<<
}

function handleWithdrawOrRelockLogic(
    MultiFeeDistributionStorage storage $,
    address _user,
    bool _isRelock,
    uint256 _limit
) external returns (uint256 amount) {
    // ...
    if (_isRelock) {
        stakeLogic($, amount, _user, $.defaultLockIndex[_user], true); // <<<
    }
    // ...
}
```
Inside of MFDBase::claimBounty(), MFDLogic::handleWithdrawOrRelockLogic() is called. If MFDBase::claimBounty() is called and the user for which that function is called has the auto relock enabled, the amount that is withdrawn will be relocked by calling MFDLogic::stakeLogic(). However, MFDBase::claimBounty() calls DefiAppStaker::_beforeWithdrawExpiredLocks() even if the amount is going to be relocked anyway. This leads to a accounting mismatch between the balance that is staked in the gauge and the balance that is staked by the user and stored in the userBalances mapping. If the user wants to withdraw the funds, the transaction will revert as the call to withdraw from the gauge inside of DefiAppStaker::_beforeWithdrawExpiredLocks() reverts due to an underflow.

Impact Explanation:
High, as the user will not be able to withdraw. This causes a loss of funds.

## Proof of Concept

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;
import {console} from "forge-std/console.sol";
import {StakingFixture} from "./StakingFixture.t.sol";
import {PublicSaleFixture} from "./PublicSaleFixture.t.sol";
import {Balances} from "../src/dependencies/MultiFeeDistribution/MFDDataTypes.sol";
import {EpochParams, EpochStates, MerkleUserDistroInput, StakingParams} from "../src/DefiAppHomeCenter.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IBountyManager} from "./../../src/interfaces/staker/IBountyManager.sol";
import {stdError} from "forge-std/Test.sol";

contract POC_bounty is StakingFixture, PublicSaleFixture {
    MockBountyManager public BountyManager;

    function setUp() public override(StakingFixture, PublicSaleFixture) {
        StakingFixture.setUp();
        PublicSaleFixture.setUp();
        BountyManager = new MockBountyManager();
    }

    function test_withdraw_reverts() public {
        // Example User flow: they "zap" into staking
        uint256 amount = 1 ether;
        load_weth9(User1.addr, amount, weth9);
        uint256 lpAmount;
        vm.startPrank(User1.addr);
        {
            weth9.approve(address(lockzap), amount);
            (,, uint256 minLpTokens) = vAmmPoolHelper.quoteAddLiquidity(0, amount);
            console.log("minLpTokens", minLpTokens);
            lpAmount = lockzap.zap(
                amount, // weth9Amt
                0, // emissionTokenAmt
                ONE_MONTH_TYPE_INDEX, // lockTypeIndex
                minLpTokens // slippage check
            );
        }
        vm.stopPrank();
        assertEq(lpAmount, IERC20(address(gauge)).balanceOf(address(staker)));
        Balances memory userBalances = staker.getUserBalances(User1.addr);
        assertEq(lpAmount, userBalances.total);
        assertEq(lpAmount, userBalances.locked);
        assertEq(0, userBalances.unlocked);
        assertEq(lpAmount * ONE_MONTH_MULTIPLIER, userBalances.lockedWithMultiplier);
        assertEq(center.getUserConfig(User1.addr).receiver, User1.addr);
        uint256 balanceUser = gauge.balanceOf(address(staker));
        assertEq(balanceUser, lpAmount);
        vm.startPrank(Admin.addr);
        staker.setBountyManager(address(BountyManager));
        vm.stopPrank();
        vm.warp(block.timestamp + 2 days);
        vm.startPrank(Admin.addr);
        staker.removeReward(0x0000000000000000000000000000000000000400);
        staker.addReward(address(usdc));
        usdc.mint(Admin.addr, 1 ether);
        usdc.approve(address(staker), 1 ether);
        staker.distributeAndTrackReward(address(usdc), 1 ether);
        vm.stopPrank();
        vm.warp(block.timestamp + 60 days);
        vm.startPrank(User1.addr);
        staker.setAutoRelock(true);
        vm.stopPrank();
        // claimBounty is called which calls _beforeWithdrawExpiredLocks and withdraws from gauge
        // but the amount is staked again due to autoRelockDisabled == false
        vm.startPrank(address(BountyManager));
        staker.claimBounty(User1.addr, true);
        vm.stopPrank();
        // gauge does not have any funds even though user staked
        assertEq(0, IERC20(address(gauge)).balanceOf(address(staker)));
        Balances memory userBalancesAfter = staker.getUserBalances(User1.addr);
        assertEq(lpAmount, userBalancesAfter.total);
        assertEq(lpAmount, userBalancesAfter.locked);
        assertEq(0, userBalancesAfter.unlocked);
        assertEq(lpAmount, userBalancesAfter.lockedWithMultiplier);
        assertEq(center.getUserConfig(User1.addr).receiver, User1.addr);
        vm.warp(block.timestamp + 60 days);
        // call to withdraw reverts due to underflow
        vm.startPrank(User1.addr);
        vm.expectRevert(stdError.arithmeticError);
        staker.withdrawExpiredLocks();
        vm.stopPrank();
    }
}

contract MockBountyManager is IBountyManager {
    constructor() {}
    /// @inheritdoc IBountyManager
    function quote(address _param) external returns (uint256 bounty){}
    /// @inheritdoc IBountyManager
    function claim(address _param) external returns (uint256 bounty){}
    /// @inheritdoc IBountyManager
    function minDLPBalance() external view returns (uint256 amt){
        amt = 0;
    }
    /// @inheritdoc IBountyManager
    function executeBounty(address _user, bool _execute, uint256 _actionType)
        external
        returns (uint256 bounty, uint256 actionType){}
}
```

## Recommendation

Only call _beforeWithdrawExpiredLocks() inside of claimBounty() if the funds are not going to be relocked.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting mismatch that occurs when a user with auto‑relock enabled calls the claimBounty function. ClaimBounty internally invokes MFDLogic.handleWithdrawOrRelockLogic, which decides whether the withdrawn amount should be restaked. However, the implementation also calls DefiAppStaker._beforeWithdrawExpiredLocks unconditionally, even when the amount is going to be relocked. _beforeWithdrawExpiredLocks pulls any pending rewards and then withdraws the specified amount from the external gauge contract. Because the same amount is immediately restaked by stakeLogic, the gauge’s actual token balance is reduced to zero while the internal userBalances mapping still records the full locked amount. When the user later attempts to withdraw their expired locks, the gauge withdrawal underflows, causing the transaction to revert with an arithmetic error. From the user’s perspective the UI shows that their total locked balance is unchanged, but the gauge balance is zero and any attempt to withdraw returns nothing or reverts, effectively making the funds disappear. The bug is triggered only when auto‑relock is enabled and claimBounty is called; otherwise the flow works as intended. It was discovered during a formal audit and reproduced with a Forge test that asserted the revert. The issue is hard to notice because the internal accounting still appears correct, masking the fact that the external gauge no longer holds the tokens. This class of bug falls under accounting mismatches or double‑withdrawal errors that lead to underflow conditions. The correct mitigation is to call _beforeWithdrawExpiredLocks only when the withdrawn amount is not being immediately restaked, i.e., guard the call with a condition that checks the auto‑relock flag, thereby keeping the external gauge balance in sync with the internal accounting and preventing withdrawal reverts.
