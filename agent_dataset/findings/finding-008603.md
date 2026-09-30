---
id: 8603
severity: "Critical"
---

# Scaling Of UD60x18 Variables Sent to _calculateVotingPower() Causes Incorrect Calculations

## Description

The _calculateVotingPower() function uses the UD60x18 user type from PaulRBerg library. in the example on the site we can see that all inputs are scaled to have E18 added to them as in UD60x18. This is not so in the current implementation and the variables sent in from other calls are never scaled correctly, thus the calculation only ever returns the value of the Staked amount no matter what the remaining Stake lock time is.

The voting power calculations are static to the stake amount and can be manipulated. The voting power also never decays based on remaining lock time.

## Proof of Concept

Currently no matter what the remaining time is the voting power is always the сtaked value:
[PASS] test_StakeGetVotingPowerSecondStaker() (gas: 441673)
Logs:
[SecondStakerTest] Locked for Max - 1 week with Stake of 120000000--> Voting Power of User1 is: 120000000
[SecondStakerTest] Locked for Min duration with Stake of 144400000 --> Voting Power of User2 is: 144400000
VM WARP ADDING MIN DURATION + 1
New values for voting power are:
[SecondStakerTest] Locked for Max - 1 week with Stake of 120000000--> Voting Power of User1 is: 120000000
[SecondStakerTest] Locked for Min duration with Stake of 144400000 --> Voting Power of User2 is: 144400000

Code
```solidity
function test_StakeGetVotingPowerSecondStaker() external {
    // it should revert
    vm.startPrank(User1);
    mockLPToken.approve(proxy, 120000000);
    VeGuan(proxy).stakeAndMint(120000000, MAX_LOCK_DURATION - 1 weeks);
    vm.stopPrank();
    vm.startPrank(User2);
    mockLPToken.approve(proxy, 144400000);
    VeGuan(proxy).stakeAndMint(144400000, MIN_LOCK_DURATION);
    vm.stopPrank();
    (uint256 scalingFactor, uint256 votingPower) = VeGuan(proxy).getVotingPowerOf(1);
    console.log("[SecondStakerTest] Locked for Max - 1 week with Stake of 120000000--> Voting Power of User1 is: %d", votingPower);
    (scalingFactor, votingPower) = VeGuan(proxy).getVotingPowerOf(2);
    console.log("[SecondStakerTest] Locked for Min duration with Stake of 144400000 --> Voting Power of User2 is: %d", votingPower);
    console.log("VM WARP ADDING MIN DURATION + 1");
    vm.warp(MIN_LOCK_DURATION + 1);
    console.log("New values for voting power are:");
    (scalingFactor, votingPower) = VeGuan(proxy).getVotingPowerOf(1);
    console.log("[SecondStakerTest] Locked for Max - 1 week with Stake of 120000000--> Voting Power of User1 is: %d", votingPower);
    (scalingFactor, votingPower) = VeGuan(proxy).getVotingPowerOf(2);
    console.log("[SecondStakerTest] Locked for Min duration with Stake of 144400000 --> Voting Power of User2 is: %d", votingPower);
}
```
Result
Once corrected it gives changed values:
[PASS] test_StakeGetVotingPowerSecondStaker() (gas: 443767)
Logs:
[SecondStakerTest] Locked for Max - 1 week with Stake of 120000000--> Voting Power of User1 is:
[SecondStakerTest] Locked for Min duration with Stake of 144400000 --> Voting Power of User2 is:
VM WARP ADDING MIN DURATION + 1
New values for voting power are:
[SecondStakerTest] Locked for Max - 1 week with Stake of 120000000--> Voting Power of User1 is:
[SecondStakerTest] Locked for Min duration with Stake of 144400000 --> Voting Power of User2 is: 144400000000000000000000000

## Recommendation

Scale the values each time the function is called to be value * 1E18:
```solidity
function getVotingPowerOf(uint256 tokenId) public view returns (uint256 scalingFactor, uint256 votingPower) {
    // load veGUAN's storage pointer
    VeGuanStorage storage $ = _getVeGuanStorage();
    // load the locked position's storage pointer
    LockedPositionData storage lockedPosition = _getVeGuanStorage().lockedPositions[tokenId];
    uint256 votingCurveCorrected = $.votingPowerCurveAFactor * 1e18;
    // calculate how many seconds are left until the position is unlocked, used to determine the voting power
    // note: if the position is unlocked, the following value is set as 0 which returns a voting power of 0
    uint256 remainingLockDuration = block.timestamp > lockedPosition.lockedUntil ? 0 : lockedPosition.lockedUntil - block.timestamp;
    remainingLockDuration = remainingLockDuration * 1E18;
    return _calculateVotingPower(
        ud60x18(votingCurveCorrected),
        ud60x18(remainingLockDuration),
        ud60x18(lockedPosition.stake * 1E18)
    );
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect handling of fixed‑point numbers when calculating voting power in the veGUAN staking contract. The contract uses the UD60x18 type from the PaulRBerg library, which expects values to be scaled by 1e18 before any arithmetic is performed. In the current implementation the function that ultimately computes voting power, _calculateVotingPower, receives three arguments – the voting curve factor, the remaining lock duration and the staked amount – that are not multiplied by 1e18. As a result the fixed‑point arithmetic collapses to a simple identity operation and the function returns a value that is equal to the raw stake amount, completely ignoring the lock‑time component. This mismatch is the root cause: a unit‑conversion error where the contract treats already‑scaled values as if they were unscaled, leading to a loss of the intended time‑based weighting. An attacker can exploit the bug by staking any amount and receiving voting power that is exactly the stake, regardless of how short or long the lock period is. Because the voting power never decays when the lock expires, a user can lock for the minimum duration, obtain the same voting weight as a long‑term locker, and later manipulate governance proposals without any penalty. The impact is that governance decisions can be skewed, protocol parameters may be altered by parties with insufficient economic commitment, and the economic model that relies on time‑weighted voting is broken. The bug manifests whenever getVotingPowerOf is called – the contract reads the stored lock duration, multiplies it by 1e18 only after the fact, but then passes the unscaled value to the calculator, so the returned voting power is static. All token holders, especially those relying on voting power for proposal creation or voting, are affected because the UI will display a voting power that matches the stake amount, contradicting the expectation that longer locks yield higher power and that power decreases after expiry. The issue was discovered during a security audit when unit tests showed that advancing the blockchain timestamp did not change the reported voting power, confirming that the lock time was ignored. The problem is subtle because the returned numbers are plausible and no revert or error occurs; only a careful comparison of expected versus actual values reveals the discrepancy. To remediate, each argument supplied to _calculateVotingPower must be scaled by 1e18 (i.e., multiplied by the fixed‑point factor) before the call, ensuring that the voting curve factor, remaining lock duration and stake are interpreted correctly as UD60x18 values. After scaling, the voting power will correctly reflect both the amount staked and the remaining lock time, and will decay to zero once the lock expires, restoring the intended economic incentives and protocol safety.
