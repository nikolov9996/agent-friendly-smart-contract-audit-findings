---
id: 22368
severity: "High"
---

# Users can fully drain the TrufVesting contract

## Description

Due to flaw in the logic in claimable any arbitrary user can drain all the funds within the contract. A user's claimable is calculated in the following way:
1. Up until start time it is 0.
2. Between start time and cliff time it's equal to initialRelease.
3. After cliff time, it linearly increases until the full period ends.
However, if we look at the code, when we are at stage 2., it always returns initialRelease, even if we've already claimed it. This would allow for any arbitrary user to call claim as many times as they wish and every time they'd receive initialRelease. Given enough iterations, any user can drain the contract.

```solidity
function claimable(uint256 categoryId, uint256 vestingId, address user)
public
view
returns (uint256 claimableAmount)
{
    UserVesting memory userVesting = userVestings[categoryId][vestingId][user];
    VestingInfo memory info = vestingInfos[categoryId][vestingId];
    uint64 startTime = userVesting.startTime + info.initialReleasePeriod;
    if (startTime > block.timestamp) {
        return 0;
    }
    uint256 totalAmount = userVesting.amount;
    uint256 initialRelease = (totalAmount * info.initialReleasePct) / DENOMINATOR;
    startTime += info.cliff;
    if (startTime > block.timestamp) {
        return initialRelease;
    }
}

function claim(address user, uint256 categoryId, uint256 vestingId, uint256 claimAmount) public {
    if (user != msg.sender && (!categories[categoryId].adminClaimable || msg.sender != owner())) {
        revert Forbidden(msg.sender);
    }
    uint256 claimableAmount = claimable(categoryId, vestingId, user);
    if (claimAmount == type(uint256).max) {
        claimAmount = claimableAmount;
    } else if (claimAmount > claimableAmount) {
        revert ClaimAmountExceed();
    }
    if (claimAmount == 0) {
        revert ZeroAmount();
    }
    categories[categoryId].totalClaimed += claimAmount;
    userVestings[categoryId][vestingId][user].claimed += claimAmount;
    trufToken.safeTransfer(user, claimAmount);
    emit Claimed(categoryId, vestingId, user, claimAmount);
}
```

Any user can drain the contract

## Proof of Concept

```solidity
function test_cliffVestingDrain() public {
    _setupVestingPlan();
    uint256 categoryId = 2;
    uint256 vestingId = 0;
    uint256 stakeAmount = 10e18;
    uint256 duration = 30 days;
    vm.startPrank(owner);
    vesting.setUserVesting(categoryId, vestingId, alice, 0, stakeAmount);
    vm.warp(block.timestamp + 11 days);
    // warping 11 days, because initial release period is 10 days
    // and cliff is at 20 days. We need to be in the middle
    vm.startPrank(alice);
    assertEq(trufToken.balanceOf(alice), 0);
    vesting.claim(alice, categoryId, vestingId, type(uint256).max);
    uint256 balance = trufToken.balanceOf(alice);
    assertEq(balance, stakeAmount * 5 / 100);
    // Alice should be able to have claimed just 5% of the vesting
    for (uint i; i < 39; i++ ){
        vesting.claim(alice, categoryId, vestingId, type(uint256).max);
    }
    uint256 newBalance = trufToken.balanceOf(alice);
    // Alice has claimed 2x the amount she was supposed to be vested.
    assertEq(newBalance, stakeAmount * 2);
    // In fact she can keep on doing this to drain the whole contract
}
```

## Recommendation

change the if check to the following
```solidity
if (startTime > block.timestamp) {
    if (initialRelease > userVesting.claimed) {
        return initialRelease - userVesting.claimed;
    }
    else { return 0; }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerabilityis an accounting flaw in the vesting contract that lets any participant withdraw more tokens than they are entitled to. The contract calculates the amount a user can claim in three phases: before the start time it returns zero, between the start time and the cliff it returns a fixed initialRelease amount, and after the cliff it linearly releases the remaining balance. The view function that reports the claimable amount contains a logic error: during the second phase it always returns the full initialRelease value without subtracting the amount that the user has already claimed. Because the claim function relies on this view to enforce limits, a user can call claim repeatedly while the blockchain timestamp is between the start+initialReleasePeriod and the cliff, and each call will be accepted as a valid claim of the full initialRelease amount. By iterating this call enough times the attacker can drain the entire token balance held by the contract. The bug manifests only when the current block timestamp falls after the initial release period but before the cliff expires, which is a narrow window defined by the vesting schedule. Any address that holds a vesting entry can exploit it, so all token holders and the protocol itself are at risk of losing funds. The issue was discovered during a manual audit and confirmed with a proof‑of‑concept test that repeatedly called claim and observed the token balance growing to twice the expected amount and eventually to the full contract balance. The problem is hard to notice because the view function returns a non‑zero amount that looks correct for the first claim, and the claim function does not perform an additional check against the user’s claimed total. The vulnerability belongs to the class of incorrect accounting or double‑spend bugs where state is not taken into account when computing entitled amounts. From a user perspective the contract appears to allow normal withdrawals, but the user sees their token balance increase far beyond the scheduled release and the contract balance shrink to zero, contradicting the expectation that only the initial release should be claimable once. The proper fix is to modify the claimable calculation to subtract the amount already claimed (for example returning initialRelease‑userVesting.claimed when the timestamp is still in the cliff period) and to ensure the linear release logic also respects previously claimed tokens. This change restores correct accounting and prevents arbitrary draining of the contract.
