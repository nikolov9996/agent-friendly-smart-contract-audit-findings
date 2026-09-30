---
id: 4551
severity: "High"
---

# The calculation of the total weight in the TokenLocker is incorrect Submitted by etherSky, also found by pkqs90, 0xNirix and 0xDjango

## Description

```solidity
I will explain the issue using an example from the proof of concept. At week 1, User 1 and User 2 each lock 100 tokens for 10 weeks. Initially, the total weight and individual weights of both users are 0.
• TokenLocker.sol#L608-L611:
function _lock(address _account, uint256 _amount, uint256 _weeks) internal {
    uint256 frozen = accountData.frozen;
    if (frozen > 0) {
        accountData.frozen = SafeCast.toUint32(frozen + _amount);
        _weeks = MAX_LOCK_WEEKS;
    }
    else {
        if (_weeks == 1 && block.timestamp % 1 weeks > 4 days) _weeks = 2;
        accountData.locked = SafeCast.toUint32(accountData.locked + _amount);
        totalDecayRate = SafeCast.toUint32(totalDecayRate + _amount);
    }
    accountWeeklyWeights[_account][systemWeek] = SafeCast.toUint40(accountWeight + _amount * _weeks);
    totalWeeklyWeights[systemWeek] = SafeCast.toUint40(totalWeight + _amount * _weeks);
}
– Line 587: The locked value for both users is updated to 100.
– Line 590: The totalDecayRate is set to 200, which represents the total weight decay per week.
This means the total weight would be 2000 at week 1, 1800 at week 2, and so on.
– Line 608: The weights of User 1 and User 2 are each calculated as 1000.
– Line 611: The total weight is updated to 2000, which correctly matches the sum of both users' weights.
The total weight at week 1 => 2000
User1 weight at week 1 => 1000
User2 weight at week 1 => 1000
At week 2, User 1 attempts to withdraw all their tokens with a penalty.
• TokenLocker.sol#L1184-L1190:
function withdrawWithPenalty(uint256 amountToWithdraw) external notFrozen(msg.sender) returns (uint256 output) {
    accountData.locked -= lockedPlusPenalties;
    totalDecayRate -= lockedPlusPenalties;
    systemWeek = getWeek();
    accountWeeklyWeights[msg.sender][systemWeek] = SafeCast.toUint40(weight - decreasedWeight);
    totalWeeklyWeights[systemWeek] = SafeCast.toUint40(getTotalWeightWrite() - decreasedWeight);
}
– Line 1184: User 1's locked value is set to 0.
– Line 1185: The totalDecayRate is reduced by 100, making it 100.
– Line 1189: User 1's weight becomes 0, as all tokens have been withdrawn.
– Line 1190: The getTotalWeightWrite function is called, but the issue arises because the totalDecayRate had already been updated in line 1185, leading to incorrect calculations.
• TokenLocker.sol#L513:
function getTotalWeightWrite() public returns (uint256 weightOut) {
    while (updatedWeek < week) {
        updatedWeek++;
        weight -= rate;
        totalWeeklyWeights[updatedWeek] = weight;
        rate -= totalWeeklyUnlocks[updatedWeek];
    }
    totalDecayRate = rate;
    totalUpdatedWeek = SafeCast.toUint16(week);
    weightOut = weight;
}
– Line 513: The total weight for week 2 is incorrectly calculated as 1900, because the totalDecayRate used is 100 instead of the expected 200. This happens because the decay rate for User 1 should have remained at its week 1 value but was prematurely removed before being applied.
As a result, the total weight for week 2 in the withdrawWithPenalty function is computed as 1000 in line 1190 (1900 - 900). The specific log from the PoC confirms this issue,
The total weight at week 2 => 1000
User1 weight at week 2 => 
User2 weight at week 2 => 
*************************
The total weight at week 3 => 
User1 weight at week 3 => 
User2 weight at week 3 => 
It shows that the total voting weight becomes larger than the sum of the individual users' weights, with the discrepancy growing over time.
```

Impact Explanation:
In a DAO, accurately calculating the total weights and individual users' weights is critical. Due to this issue, the discrepancy between the total weight and the sum of individual weights can grow indefinitely, which could ultimately disrupt the proposal system within the DAO.

## Proof of Concept

```solidity
Please add the following test file to the test/foundry directory:
// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;
// test setup
import {TestSetup, IBimaVault, ITokenLocker} from "./TestSetup.sol";
import "forge-std/console2.sol";
contract TokenLockerTest1 is TestSetup {
    function setUp() public virtual override {
        super.setUp();
        // setup the vault to get BimaTokens which are used for voting
        uint128[] memory _fixedInitialAmounts;
        IBimaVault.InitialAllowance[] memory initialAllowances = new IBimaVault.InitialAllowance[](2);
        uint256 tokenAmounts = 100 * INIT_LOCK_TO_TOKEN_RATIO;
        // give user1 allowance
        initialAllowances[0].receiver = users.user1;
        initialAllowances[0].amount = tokenAmounts;
        // give user2 allowance
        initialAllowances[1].receiver = users.user2;
        initialAllowances[1].amount = tokenAmounts;
        vm.prank(users.owner);
        bimaVault.setInitialParameters(
            emissionSchedule,
            boostCalc,
            INIT_BAB_TKN_TOTAL_SUPPLY,
            INIT_VLT_LOCK_WEEKS,
            _fixedInitialAmounts,
            initialAllowances
        );
        // transfer voting tokens to recipients
        vm.prank(users.user1);
        bimaToken.transferFrom(address(bimaVault), users.user1, tokenAmounts);
        vm.prank(users.user2);
        bimaToken.transferFrom(address(bimaVault), users.user2, tokenAmounts);
        // verify recipients have received voting tokens
        assertEq(bimaToken.balanceOf(users.user1), tokenAmounts);
        assertEq(bimaToken.balanceOf(users.user2), tokenAmounts);
    }
    function test_withdrawWithPenalty_totalDecayRate_change() external {
        vm.prank(users.owner);
        tokenLocker.setAllowPenaltyWithdrawAfter(block.timestamp + 6 weeks);
        vm.warp(tokenLocker.allowPenaltyWithdrawAfter() + 1);
        vm.prank(users.owner);
        tokenLocker.setPenaltyWithdrawalsEnabled(true);
        /**
        Penalty withdrawal has been enabled.
        */
        assertEq(tokenLocker.penaltyWithdrawalsEnabled(), true);
        uint256 tokenAmounts = 100 * INIT_LOCK_TO_TOKEN_RATIO;
        uint256 weekLocks = 10;
        vm.prank(users.user1);
        tokenLocker.lock(users.user1, tokenAmounts / INIT_LOCK_TO_TOKEN_RATIO, weekLocks);
        vm.prank(users.user2);
        tokenLocker.lock(users.user2, tokenAmounts / INIT_LOCK_TO_TOKEN_RATIO, weekLocks);
        /**
        The total weight at week 1: 2000
        User1 weight at week 1: 1000
        User2 weight at week 1: 1000
        */
        console2.log('The total weight at week 1 => ', tokenLocker.getTotalWeight());
        console2.log('User1 weight at week 1 => ', tokenLocker.getAccountWeight(users.user1));
        console2.log('User2 weight at week 1 => ', tokenLocker.getAccountWeight(users.user2));
        vm.warp(block.timestamp + 1 weeks);
        vm.prank(users.user1);
        /**
        User1 withdraws with a penalty at week 2.
        */
        tokenLocker.withdrawWithPenalty(type(uint256).max);
        /**
        The total weight at week 2: 1000
        User1 weight at week 2: 0
        User2 weight at week 2: 900
        */
        console2.log('*************************');
        console2.log('The total weight at week 2 => ', tokenLocker.getTotalWeight());
        console2.log('User1 weight at week 2 => ', tokenLocker.getAccountWeight(users.user1));
        console2.log('User2 weight at week 2 => ', tokenLocker.getAccountWeight(users.user2));
        vm.warp(block.timestamp + 1 weeks);
        /**
        The total weight at week 3: 900
        User1 weight at week 3: 0
        User2 weight at week 3: 800
        */
        console2.log('*************************');
        console2.log('The total weight at week 3 => ', tokenLocker.getTotalWeight());
        console2.log('User1 weight at week 3 => ', tokenLocker.getAccountWeight(users.user1));
        console2.log('User2 weight at week 3 => ', tokenLocker.getAccountWeight(users.user2));
    }
}
```

## Recommendation

```solidity
function withdrawWithPenalty(uint256 amountToWithdraw) external notFrozen(msg.sender) returns (uint256 output) {
    accountData.locked -= lockedPlusPenalties;
    systemWeek = getWeek();
    accountWeeklyWeights[msg.sender][systemWeek] = SafeCast.toUint40(weight - decreasedWeight);
    totalWeeklyWeights[systemWeek] = SafeCast.toUint40(getTotalWeightWrite() - decreasedWeight);
    totalDecayRate -= lockedPlusPenalties;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical accounting error in the token locker contract that manages voting weight for a DAO. The contract stores a total decay rate that represents how much voting weight should be reduced each week as locked tokens approach their unlock date. When a user withdraws their tokens with a penalty, the withdrawWithPenalty function first reduces the totalDecayRate by the amount being withdrawn and only afterwards calls getTotalWeightWrite to recompute the total voting weight for the current week. getTotalWeightWrite iterates over weeks, applying the decay rate stored in the variable "rate" to the cumulative weight. Because the totalDecayRate has already been decreased before the decay calculation runs, the function uses a lower rate than it should for the current week. Consequently the weight that is subtracted from the total is smaller than the actual decay that should have occurred, causing the total weight reported by the contract to diverge from the sum of the individual account weights. The divergence starts after the first penalty withdrawal and grows each subsequent week, eventually making the total voting power appear larger than the sum of all users’ weights. This mis‑alignment breaks the fundamental accounting assumption that total voting weight equals the aggregate of individual weights, which is essential for a DAO’s proposal and voting logic. From a user’s perspective the symptoms are that after a penalty withdrawal their own voting weight drops to zero while the overall DAO weight remains unexpectedly high, leading to proposals that either never reach quorum or are decided with an inflated weight. The issue was discovered during a formal audit by running a proof‑of‑concept test that locked equal amounts for two users, performed a penalty withdrawal, and logged the weight values week by week, revealing the mismatch. The bug is hard to notice because the contract still reports a non‑zero total weight, so the DAO appears functional, but the internal accounting is silently corrupted. The root cause is the premature update of the decay rate before the decay calculation is performed; the fix is to reorder the operations so that getTotalWeightWrite is called while the decay rate still reflects the pre‑withdrawal state, and only after the correct total weight has been written should the totalDecayRate be decreased. In abstract terms, the contract suffers from an accounting race condition where state updates are applied in the wrong order, leading to an inconsistent view of the system’s total voting power."
