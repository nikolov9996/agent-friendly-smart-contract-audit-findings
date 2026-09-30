---
id: 21979
severity: "Medium"
---

# Loss of user locked voting tokens due to unsafe downcast overflow

## Description

`TokenLocker::AccountData` [stores](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/dao/TokenLocker.sol#L41-L49) the account's current `locked`, `unlocked` and `frozen` balances using `uint32`:
```solidity
struct AccountData {
    // Currently locked balance. Each week the lock weight decays by this amount.
    uint32 locked;
    // Currently unlocked balance (from expired locks, can be withdrawn)
    uint32 unlocked;
    // Currently "frozen" balance. A frozen balance is equivalent to a `MAX_LOCK_WEEKS` lock,
    // where the lock weight does not decay weekly. An account may have a locked balance or a
    // frozen balance, never both at the same time.
    uint32 frozen;
```
Inside `TokenLocker::_lock` the input `uint256 _amount` token value which the user is locking gets unsafely [downcast](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/dao/TokenLocker.sol#L450) into `uint32`:
```solidity
accountData.locked = uint32(accountData.locked + _amount);
```
Then in `TokenLocker::_weeklyWeightWrite`, `accountData.locked` is [read](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/dao/TokenLocker.sol#L914) into a `uint256` in the calculation to update the `unlocked` amount but this is useless as the downcast has already occurred:
```solidity
uint256 locked = accountData.locked;
```
Finally in `TokenLocker::withdrawExpiredLocks` this will either [revert](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/dao/TokenLocker.sol#L765-L780) with "No unlocked tokens" if the overflow resulted in 0, or will transfer back to the user far less tokens than they initially locked up:
```solidity
function withdrawExpiredLocks(uint256 _weeks) external returns (bool) {
    _weeklyWeightWrite(msg.sender);
    getTotalWeightWrite();

    AccountData storage accountData = accountLockData[msg.sender];
    uint256 unlocked = accountData.unlocked;
    require(unlocked > 0, "No unlocked tokens");
    accountData.unlocked = 0;
    if (_weeks > 0) {
        _lock(msg.sender, unlocked, _weeks);
    } else {
        lockToken.transfer(msg.sender, unlocked * lockToTokenRatio);
        emit LocksWithdrawn(msg.sender, unlocked, 0);
    }
    return true;
}
```
Loss of user locked voting tokens due to unsafe downcast overflow.

## Proof of Concept

For a simple example, in `test/foundry/TestSetup.sol` set `INIT_BAB_TKN_TOTAL_SUPPLY` to something greater than `type(uint32).max` and set `INIT_LOCK_TO_TOKEN_RATIO = 1` eg:
```solidity
uint256 internal constant INIT_LOCK_TO_TOKEN_RATIO = 1;
uint256 internal constant INIT_BAB_TKN_TOTAL_SUPPLY = 1_000_000e18;
```
Add following test contract to `test/foundry/dao/TokenLockerTest.t.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;

// test setup
import {TestSetup, IBabelVault} from "../TestSetup.sol";

contract TokenLockerTest is TestSetup {

    function setUp() public virtual override {
        super.setUp();

        // setup the vault to get BabelTokens which are used for voting
        uint128[] memory _fixedInitialAmounts;
        IBabelVault.InitialAllowance[] memory initialAllowances
            = new IBabelVault.InitialAllowance[](1);

        // give user1 allowance over the entire supply of voting tokens
        initialAllowances[0].receiver = users.user1;
        initialAllowances[0].amount = INIT_BAB_TKN_TOTAL_SUPPLY;

        vm.prank(users.owner);
        babelVault.setInitialParameters(emissionSchedule,
                                        boostCalc,
                                        INIT_BAB_TKN_TOTAL_SUPPLY,
                                        INIT_VLT_LOCK_WEEKS,
                                        _fixedInitialAmounts,
                                        initialAllowances);

        // transfer voting tokens to recipients
        vm.prank(users.user1);
        babelToken.transferFrom(address(babelVault), users.user1, INIT_BAB_TKN_TOTAL_SUPPLY);

        // verify recipients have received voting tokens
        assertEq(babelToken.balanceOf(users.user1), INIT_BAB_TKN_TOTAL_SUPPLY);
    }

    function test_withdrawExpiredLocks_LossOfLockedTokens() external {
        // save user initial balance
        uint256 userInitialBalance = babelToken.balanceOf(users.user1);
        assertEq(userInitialBalance, INIT_BAB_TKN_TOTAL_SUPPLY);

        // assert overflow will occur
        assertTrue(userInitialBalance > uint256(type(uint32).max)+1);

        // first lock up entire user balance for 1 week
        vm.prank(users.user1);
        tokenLocker.lock(users.user1, userInitialBalance, 1);

        // advance time by 2 week
        vm.warp(block.timestamp + 2 weeks);
        uint256 weekNum = 2;
        assertEq(tokenLocker.getWeek(), weekNum);

        // withdraw without re-locking to get all locked tokens back
        vm.prank(users.user1);
        tokenLocker.withdrawExpiredLocks(0);

        // verify user received all their tokens back
        assertEq(babelToken.balanceOf(users.user1), userInitialBalance);

        // fails with 2701131776 != 1000000000000000000000000
        // user locked   1000000000000000000000000
        // user unlocked 2701131776
        // critical loss of funds
    }
}
```
Run with: `forge test --match-test test_withdrawExpiredLocks_LossOfLockedTokens -vvv`

## Recommendation

Limit the total supply of the voting token to be `<= type(uint32).max * lockToTokenRatio` and use OpenZeppelin's `SafeCast` [library](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/math/SafeCast.sol) instead of performing unsafe downcasts.
The supply limit should be placed inside `BabelVault::setInitialParameters` like this:
```solidity
// enforce invariant described in TokenLocker to prevent overflows
require(totalSupply <= type(uint32).max * locker.lockToTokenRatio(),
        "Total supply must be <= type(uint32).max * lockToTokenRatio");
```
This is actually noted in this [comment](https://github.com/Bima-Labs/bima-v1-core/blob/09461f0d22556e810295b12a6d7bc5c0efec4627/contracts/dao/TokenLocker.sol#L24-L30) but never enforced anywhere.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an integer overflow caused by an unsafe down‑cast of a user‑supplied token amount from uint256 to uint32 inside the TokenLocker contract. The contract stores each account's locked, unlocked and frozen balances in a struct that uses uint32 fields. When a user locks tokens, the function adds the supplied amount to the uint32 locked field after casting, so any amount larger than 2^32‑1 wraps around to a small value or zero. The wrapped value is later read as a uint256 for the weekly weight calculation, but the overflow has already corrupted the stored balance. When the user later calls withdrawExpiredLocks, the contract checks the unlocked balance; if the overflow produced zero the call reverts with 'No unlocked tokens', otherwise the user receives far fewer tokens than originally locked. The impact is loss of voting tokens for any user who locks an amount that exceeds the uint32 limit, effectively making their voting power disappear. The condition occurs whenever the total supply of the voting token (or a single lock) can be greater than type(uint32).max multiplied by the lock‑to‑token ratio, which is possible in the current deployment because no supply cap is enforced. The issue was discovered during a manual audit that inspected the data types and observed the down‑cast without safety checks. It is hard to notice because the contract later casts the uint32 back to uint256, masking the overflow, and the UI shows a successful lock operation even though the internal balance is corrupted. The bug belongs to the class of unsafe integer casting leading to overflow and loss of funds. From a user’s perspective the expected behavior is that after locking tokens they can withdraw the same amount after the lock expires, but in practice the balance may become zero or a tiny fraction, resulting in 'funds disappear' or 'my tokens are missing'. The fix is to keep the balances in a type that can hold the maximum possible amount (e.g., uint256) or to use OpenZeppelin’s SafeCast library to revert on overflow, and to enforce a total‑supply limit that guarantees the cast is safe.
