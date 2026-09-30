---
id: 22694
severity: "High"
---

# Revoking vesting schedule does not subtract

## Description

ZivoeVestingRewards.revokeVestingSchedule() should reduce the voting power of the user with the withdrawable amount plus the revoked amount. However, it reduces it only by the withdrawable amount. When called, revokeVestingSchedule() fetches the withdrawable amount by the user at that moment.
```solidity
uint256 amount = amountWithdrawable(account);
```
The revoke logic is executed and the user's checkpoint value is decreased by amount.
```solidity
_writeCheckpoint(_checkpoints[account], _subtract, amount);
```
The code ignores the amount that's being revoked and the user keeps more voting power than he has to. Imagine the following: totalVested = 1000 withdrawable = 0 If the schedule gets revoked, the user's checkpoint value will not be decreased at all because there is nothing to be withdrawn. The user can later use their voting power to vote on governance proposals. In fact, amountWithdrawable(account) being close to 0 has a very high likelihood because: • the user can frontrun the transaction and withdraw the tokens they are entitled to • it's highly likely that a vesting schedule will be removed shortly after creating it. However, even if amountWithdrawable() is not equal to 0, the user would still be left with more voting power. Users keep voting power that must have been taken away. POC to be run in Test_ZivoeRewardsVesting.sol
```solidity
function test_revoking_leaves_votes() public {
    assert(zvl.try_createVestingSchedule(
        address(vestZVE),
        address(moe),
        0,
        360,
        6000 ether,
        true
    ));
    // Vesting succeeded
    assertEq(vestZVE.balanceOf(address(moe)), 6000 ether);
    hevm.roll(block.number + 1);
    // User votes have increased
    assertEq(vestZVE.getPastVotes(address(moe), block.number - 1), 6000 ether);
    assert(zvl.try_revokeVestingSchedule(address(vestZVE), address(moe)));
    // Revoking succeeded
    assertEq(vestZVE.balanceOf(address(moe)), 0);
    hevm.roll(block.number + 1);
    // User votes have not been decreased at all
    assertEq(vestZVE.getPastVotes(address(moe), block.number - 1), 6000 ether);
}
```

## Proof of Concept

no poc

## Recommendation

Subtract the correct amount from the checkpoint's value
```solidity
_writeCheckpoint(_checkpoints[account], _subtract, amount);
_writeCheckpoint(_checkpoints[account], _subtract, vestingAmount - vestingScheduleOf[account].totalWithdrawn + amount);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the revocation path of a token vesting contract that also tracks voting power through checkpointed balances. When a vesting schedule is revoked, the function reads the amount that is currently withdrawable for the account and then subtracts only that amount from the stored checkpoint. The remaining portion of the vesting schedule – the tokens that were still locked but are now revoked – is never deducted from the checkpoint. As a result the account’s voting power stays equal to the original vested amount even though the token balance has been set to zero. This occurs because the revocation logic calls amountWithdrawable(account) to obtain a value that may be zero after the user has already withdrawn their entitled tokens, and then calls _writeCheckpoint(..., _subtract, amount) without also subtracting vestingAmount‑totalWithdrawn. The bug can be exploited by an attacker who first withdraws any available tokens (or front‑runs the withdrawal) and then triggers revocation; the contract will record zero reduction in voting power, allowing the attacker to continue voting with the full weight of the original vesting schedule. The impact is an inflation of governance influence: proposals can be swayed by votes that should no longer exist, breaking the intended accounting assumptions that voting power mirrors token holdings. The condition for the bug is any call to revokeVestingSchedule where the withdrawable amount is low or zero, which is common when schedules are revoked shortly after creation or after a user has claimed their vested tokens. Users are affected because they see their token balance drop to zero while their pastVotes remain unchanged, leading to a mismatch between UI balances and voting power. The issue was discovered during a systematic audit that included a test case asserting that pastVotes decrease after revocation; the assertion failed, demonstrating that votes were not reduced. The problem is subtle because the contract separates token balance from voting checkpoints, so a zero balance does not automatically trigger a vote adjustment, making the bug easy to miss in casual testing. To remediate, the revocation routine must subtract both the withdrawable amount and the remaining vested amount (total vested minus already withdrawn) from the checkpoint, ensuring that the stored voting power accurately reflects the loss of all vesting rights.
