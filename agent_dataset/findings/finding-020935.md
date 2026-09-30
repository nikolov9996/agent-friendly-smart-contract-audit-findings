---
id: 20935
severity: "High"
---

# If a gauge that a user has voted for gets removed, their voting power allocated for that gauge will be lost

## Description

When a gauge that an user has voted for gets removed by the governance, their voting power allocated for that gauge will be lost forever.

## Proof of Concept

Due to the current way the `GaugeController::vote_for_gauge_weights` function is implemented, whenever a given gauge that users have voted for gets removed, all of the voting powers allocated by those users to that gauge will be permanently lost. The same issue has actually already been reported in [this report](https://github.com/code-423n4/2023-08-verwa-findings/issues/62) from the last Code4rena audit of the codebase. 

As it can be seen from the following snippet:

```solidity
function testLostVotingPower() public {
    // prepare
    uint256 v = 10 ether;
    vm.deal(gov, v);
    vm.startPrank(gov);
    ve.createLock{value: v}(v);

    // add gauges
    gc.add_gauge(gauge1, 0);
    gc.add_type("", 0);
    gc.add_gauge(gauge2, 1);

    // all-in on gauge1
    gc.vote_for_gauge_weights(gauge1, 10000);

    // governance removes gauge1
    gc.remove_gauge_weight(gauge1);
    gc.remove_gauge(gauge1);

    // cannot vote for gauge2
    vm.expectRevert("Used too much power");
    gc.vote_for_gauge_weights(gauge2, 10000);

    // cannot remove vote for gauge1
    vm.expectRevert("Gauge not added"); // @audit remove after mitigation
    gc.vote_for_gauge_weights(gauge1, 0);

    // cannot vote for gauge2 (to demonstrate again that voting power is not removed)
    vm.expectRevert("Used too much power");  // @audit remove after mitigation
    gc.vote_for_gauge_weights(gauge2, 10000);
}
```

the recommended fix from that report has actually been implemented.

However, there are two other changes there as well. The `isValidGauge` mapping has been replaced with a new one named `gauge_types_`, which practically serves the same purpose as the old one in the context of this snippet. More importantly though, a new require statement has been added, as it can be seen on the last code line of the snippet, which checks whether the gauge type is greater than `0` and reverts otherwise. Since the gauge type for a given gauge address can only be `0`, in the case where the gauge does not actually exist (i.e. it has been removed or it was never created in the first place), this means that the implemented fix will no longer work and because of that the issue is once again present in the current implementation of the `GaugeController`.

The following coded PoC, which is a modification of the one in the above linked report verifies the existence of the issue:

```solidity
function testLostVotingPower() public {
    // prepare
    uint256 v = 10 ether;
    vm.deal(gov, v);
    vm.startPrank(gov);
    ve.createLock{value: v}(v);

    // add gauges
    gc.add_gauge(gauge1, 0);
    gc.change_gauge_weight(gauge1, 100);
    gc.add_type("", 100);
    gc.add_gauge(gauge2, 1);
    gc.change_gauge_weight(gauge2, 100);

    // all-in on gauge1
    gc.vote_for_gauge_weights(gauge1, 10000);

    // governance removes gauge1
    gc.remove_gauge_weight(gauge1);
    gc.remove_gauge(gauge1);

    // cannot vote for gauge2
    vm.expectRevert("Used too much power");
    gc.vote_for_gauge_weights(gauge2, 10000);

    // cannot remove vote for gauge1
    vm.expectRevert("Gauge not added"); // @audit remove after mitigation
    gc.vote_for_gauge_weights(gauge1, 0);

    // cannot vote for gauge2 (to demonstrate again that voting power is not removed)
    vm.expectRevert("Used too much power");  // @audit remove after mitigation
    gc.vote_for_gauge_weights(gauge2, 10000);
}
```

## Recommendation

Remove the additional require statement that checks whether the gauge type for the `_gauge_addr` is different from `0`, in order to allow users to remove their votes from removed gauges:

```solidity
function vote_for_gauge_weights(address _gauge_addr, uint256 _user_weight) external {
    require(_user_weight >= 0 && _user_weight <= 10_000, "Invalid user weight");
    require(_user_weight == 0 || gauge_types_[_gauge_addr] != 0, "Can only vote 0 on non-gauges"); // We allow withdrawing voting power from invalid (removed) gauges
    VotingEscrow ve = votingEscrow;
    (
        ,
        /*int128 bias*/
        int128 slope_, /*uint256 ts*/
    ) = ve.getLastUserPoint(msg.sender);
    require(slope_ >= 0, "Invalid slope");
    uint256 slope = uint256(uint128(slope_));
    uint256 lock_end = ve.lockEnd(msg.sender);
    uint256 next_time = ((block.timestamp + WEEK) / WEEK) * WEEK;
    require(lock_end > next_time, "Lock expires too soon");

    int128 gauge_type = gauge_types_[_gauge_addr] - 1;
    // require(gauge_type >= 0, "Gauge not added");
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is that when a gauge that a user has previously allocated voting power to is removed from the GaugeController, the protocol does not allow the user to withdraw or re‑allocate that voting power. The root cause is an additional require statement that checks gauge_types_[_gauge_addr] != 0 before permitting a call to vote_for_gauge_weights. For a removed gauge the stored type is 0, so any attempt to set the user weight to 0 (which would withdraw the vote) triggers a revert. Because the vote cannot be cleared, the user's voting power remains marked as spent on a non‑existent gauge. Consequently, subsequent attempts to vote on other active gauges fail with a “Used too much power” error, and attempts to clear the old vote fail with "Gauge not added". From the user’s perspective the transaction simply reverts, they see no refund of voting power, and the protocol appears to have “lost” their voting weight. The issue manifests only after governance removes a gauge; while voting works correctly for existing gauges, the edge case is hidden and therefore easy to miss during normal testing. It was discovered during a formal audit by Code4rena, where a test contract reproduced the condition and observed the permanent loss of voting power. The bug belongs to the class of “state‑locking” or “resource‑leak” vulnerabilities where a user‑controlled resource becomes permanently inaccessible due to improper validation logic. The impact is high because it effectively burns a user’s voting rights, reduces the effective governance power, and may skew protocol decisions. The fix is to relax the validation so that a zero weight can be submitted for any address, including removed gauges, thereby allowing users to withdraw their allocation and restore the free voting power. Removing or adjusting the require that blocks zero votes on non‑gauges resolves the issue without altering other accounting logic.
