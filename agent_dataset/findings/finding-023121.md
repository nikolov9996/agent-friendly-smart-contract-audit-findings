---
id: 23121
severity: "High"
---

# ve_supply is updated incorrectly due to flawed time check

## Description

An incorrect time check causes ve_supply[t] to be updated incorrectly. When RewardsDistributorV2#checkpoint_total_supply() is called, the total supply at time t will be stored in ve_supply[t] for future distribution reward calculations:
```solidity
function _checkpoint_total_supply() internal {
    address ve = voting_escrow;
    uint t = time_cursor;
    uint rounded_timestamp = block.timestamp / WEEK * WEEK;
    IVotingEscrow(ve).checkpoint();
    for (uint i = 0; i < 20; i++) {
        if (t > rounded_timestamp) {
            break;
        } else {
            uint epoch = _find_timestamp_epoch(ve, t);
            IVotingEscrow.Point memory pt = IVotingEscrow(ve).point_history(epoch);
            int128 dt = 0;
            if (t > pt.ts) {
                dt = int128(int256(t - pt.ts));
            }
            ve_supply[t] = Math.max(uint(int256(pt.bias - pt.slope * dt)), 0);
        }
        t += WEEK;
    }
    time_cursor = t;
}
```
ve_supply[t] should be only updated when t week has end (t + 1 weeks <= block.timestamp). However, ve_supply[t] could be updated incorrectly when block.timestamp % 1 weeks is 0. If a veNFT is created immediately after checkpoint_total_supply() is called, its balance will not be accounted for in ve_supply[t]. A malicious user could exploit this flaw to steal future distribution rewards.
Copy below codes to RewardsDistributorV2.t.sol and run forge test --match-test testStealFutureDistributeReward
```solidity
function testStealFutureDistributeReward() public {
    initializeVotingEscrow();
    vm.warp((block.timestamp + 1 weeks) / 1 weeks * 1 weeks);
    minter.update_period();
    // distribution reward
    flowDaiPair.approve(address(escrow), 2e18);
    escrow.create_lock(2e18,50 weeks);
    DAI.transfer(address(distributor), 10e18);
    vm.warp(block.timestamp + 1 weeks);
    // tokens_per_week
    minter.update_period();
    // distribution reward
    assertApproxEqAbs(distributor.claimable(3), 10e18, 0.2e18);
    distributor.claim(3);
    assertLt(DAI.balanceOf(address(distributor)), 0.2e18);
    assertEq(distributor.claimable(1), 5e18);
    vm.expectRevert();
    distributor.claim(1);
}
```
A malicious user could create a new veNFT to steal future distribution rewards, leaving other eligible users without any rewards to claim.

## Proof of Concept

no poc

## Recommendation

Make sure that ve_supply[t] should be only updated when t week has end (t + 1 weeks <= block.timestamp):
```solidity
function _checkpoint_total_supply() internal {
    address ve = voting_escrow;
    uint t = time_cursor;
    uint rounded_timestamp = block.timestamp / WEEK * WEEK;
    IVotingEscrow(ve).checkpoint();
    for (uint i = 0; i < 20; i++) {
        if (t >= rounded_timestamp) {
            break;
        } else {
            uint epoch = _find_timestamp_epoch(ve, t);
            IVotingEscrow.Point memory pt = IVotingEscrow(ve).point_history(epoch);
            int128 dt = 0;
            if (t > pt.ts) {
                dt = int128(int256(t - pt.ts));
            }
            ve_supply[t] = Math.max(uint(int256(pt.bias - pt.slope * dt)), 0);
        }
        t += WEEK;
    }
    time_cursor = t;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect time check in the reward distribution contract that updates the stored ve token supply for a given week even when the week has not yet finished. The root cause is the condition if (t > rounded_timestamp) break which allows the loop to execute when block.timestamp is exactly on a week boundary, causing ve_supply[t] to be written before the week ends. An attacker can call checkpoint_total_supply, then immediately mint a new veNFT whose lock starts in the same week; because the supply for that week was already recorded without the new lock, the attacker’s lock is omitted from the supply snapshot. Later, when rewards are calculated based on ve_supply[t], the attacker receives a larger share of the distribution because the denominator is artificially low, effectively stealing future rewards that should belong to other participants. This can be triggered whenever the contract is called at the exact moment when block.timestamp is a multiple of one week, which can be forced by advancing time in tests or by waiting for the blockchain to reach that timestamp. The affected parties are all users of the voting escrow and reward distributor, whose expected reward share is reduced or becomes zero. The issue was discovered during a formal audit by reviewing the checkpoint logic and reproducing the scenario with a forge test that creates a lock immediately after a checkpoint. The bug is subtle because the condition appears to guard against future timestamps, yet the equality case is missed, making the error visible only at precise week boundaries. The proper fix is to change the loop condition to if (t >= rounded_timestamp) break so that the supply snapshot is only updated after the week has fully elapsed. This ensures that ve_supply[t] reflects the true total locked balance at the end of each week, preserving the accounting invariants of the reward distribution. From a user perspective, a participant may notice that after a week of locking tokens they receive no reward or a smaller amount than expected, while an attacker can claim the full reward for that week. The vulnerability belongs to the class of time‑boundary logic errors that lead to incorrect accounting snapshots and reward theft.
