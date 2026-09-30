---
id: 19210
severity: "High"
---

# It is possible to DoS all the functions related to some gauge in `GaugeController`

## Description

`_get_weight` function is used in order to return the total gauge’s weight and it also updates past values of the `points_weight` mapping, if `time_weight[_gauge_addr]` is less or equal to the `block.timestamp`. It contains the following loop:

```solidity
for (uint256 i; i < 500; ++i) {
    if (t > block.timestamp) break;
    t += WEEK;
    uint256 d_bias = pt.slope * WEEK;
    if (pt.bias > d_bias) {
        pt.bias -= d_bias;
        uint256 d_slope = changes_weight[_gauge_addr][t];
        pt.slope -= d_slope;
    } else {
        pt.bias = 0;
        pt.slope = 0;
    }
    points_weight[_gauge_addr][t] = pt;
    if (t > block.timestamp) time_weight[_gauge_addr] = t;
}
```

There are two possible scenarios:

  * `pt.bias > d_bias`
  * `pt.bias <= d_bias`

The first scenario will always happen naturally, since `pt.bias` will be the total voting power allocated for some point and since slope is a sum of all users’ slopes and slopes are calculated in such a way that `<SLOPE> * <TIME_TO_END_OF_STAKING_PERIOD> = <INITIAL_BIAS>`.

However, it is possible to artificially change `points_weight[_gauge_addr][t].bias` by calling `change_gauge_weight` (which can be only called by the governance). It important to notice here, that `change_gauge_weight` **doesn’t modify** `points_weight[_gauge_addr][t].slope`

`change_gauge_weight` does permit to change the weight to a smaller number than its current value, so it’s both perfectly legal and possible that governance does this at some point (it could be changing the weight to `0` or any other value smaller than the current one).

Then, at some point when `_get_weight` is called, we will enter the `else` block because `pt.bias` will be less than the sum of all user’s biases (since originally these values were equal, but `pt.bias` was lowered by the governance). It will set `pt.bias` and `pt.slope` to `0`.

After some time, the governance may realise that the gauge’s weight is `0`, but should be bigger and may change it to some bigger value.

We will have the situation where `points_weight[_gauge_addr][t].slope = 0` and `points_weight[_gauge_addr][t].bias > 0`.

If this happens and there is any nonzero `changes_weight[_gauge_addr]` not yet taken into account (for instance in the week after the governance update), then all the functions related to the gauge at `_gauge_addr` will not work.

It’s because, the following functions:

  * `checkpoint_gauge`
  * `gauge_relative_weight_write`
  * `gauge_relative_weight`
  * `_change_gauge_weight`
  * `change_gauge_weight`
  * `vote_for_gauge_weights`
  * `remove_gauge`

call `_get_weight` at some point.

Let’s see what will happen in `_get_weight` when it’s called:

```solidity
uint256 d_bias = pt.slope * WEEK;
if (pt.bias > d_bias) {
    pt.bias -= d_bias;
    uint256 d_slope = changes_weight[_gauge_addr][t];
    pt.slope -= d_slope;
} else {
```

We will enter the `if` statement, because `pt.bias` will be `> 0` and `pt.slope` will be `0` (or some small value, if users give their voting power to gauge in the meantime), since it was previously set to `0` in the `else` statement and wasn’t touched when gauge’s weight was changed by the governance. We will:

  * Subtract `d_bias` from `pt.bias` which will succeed
  * Attempt to subtract `changes_weight[_gauge_addr][t]` from `d_slope`

However, there could be a user (or users) whose voting power allocation finishes at `t` for some `t` not yet handled. It means that `changes_weight[_gauge_addr][t] > 0` (and if `pt.slope` is not `0`, then `changes_weight[_gauge_addr][t]` still may be greater than it).

If this happens, then the integer underflow will happen in `pt.slope -= d_slope;`. It will now happen in **every** call to `_get_weight` and it won’t be possible to recover, because:

  * `vote_for_gauge_weights` will revert
  * `change_gauge_weight` will revert

as they call `_get_weight` internally. So, it won’t be possible to modify `pt.slope` and `pt.bias` for any point in time, so the `revert` will always happen for that gauge. It won’t even be possible to remove that gauge.

So, in short, the scenario is as follows:

  1. Users allocate their voting power to a gauge `X`.
  2. Governance at some point decreases the weight of `X`.
  3. Users withdraw their voting power as the time passes, and finally the weight of `X` drops to `0`.
  4. Governance realises this and increases weight of `X` since it wants to incentivise users to provide liquidity in `X`.
  5. Voting power delegation of some user(s) ends some time after that and `_get_weight` attempts to subtract `changes_weight[_gauge_addr][t]` from the current slope (which is either `0` or some small value) and it results in integer underflow.
  6. `X` is unusable and it’s impossible to withdraw voting power from (so users cannot give their voting power somewhere else). The weight of `X` cannot be changed anymore and `X` cannot be even removed.

**Note that it is also possible to frontrun the call to`change_gauge_weight` when the weight is set to a lower value** - user with a lot of capital can watch the mempool and if weight is lowered to some value `x`, he can give a voting power of `x` to that gauge. Then, right after weight is changed by the governance, he can withdraw his voting power, leaving the gauge with weight = `0`. Then, governance will manually increase the weight to recover and DoS will happen as described. **So it is only needed that governance decreases gauge’s weight at some point**.

## Proof of Concept

Please run the test below. The test shows slightly simplified situation where governance just sets weight to `0` for `gauge1`, but as I’ve described above, it suffices that it’s just changed to a smaller value and it may drop to `0` naturally as users withdraw their voting power. The following import will also have to be added: `import {Test, stdError} from "forge-std/Test.sol";`.

```solidity
function testPoC1() public
    {
        // gauge is being set up
        vm.startPrank(gov);
        gc.add_gauge(gauge1);
        gc.change_gauge_weight(gauge1, 0);
        vm.stopPrank();

        // `user1` pays some money and adds his power to `gauge1`
        vm.startPrank(user1);
        ve.createLock{value: 1 ether}(1 ether);
        gc.vote_for_gauge_weights(gauge1, 10000);
        vm.warp(block.timestamp + 10 weeks);
        gc.checkpoint_gauge(gauge1);
        vm.stopPrank();

        // `user2` does the same
        vm.startPrank(user2);
        ve.createLock{value: 1 ether}(1 ether);
        gc.vote_for_gauge_weights(gauge1, 10000);
        vm.warp(block.timestamp + 1 weeks);
        gc.checkpoint_gauge(gauge1);
        vm.stopPrank();

        vm.warp(block.timestamp + 1825 days - 14 weeks);
        vm.startPrank(gov);
        // weight is changed to `0`, just to simplify
        // normally, weight would just be decreased here and then subsequently decreased by users when their
        // locking period is over until it finally drops to `0`
        // alternatively, some whale can frontrun a call to `change_gauge_weight` as described and then
        // withdraw his voting power leaving the gauge with `0` slope and `0` bias
        gc.change_gauge_weight(gauge1, 0);
        vm.warp(block.timestamp + 1 weeks);
        
        // now, weight is changed to some bigger value
        gc.change_gauge_weight(gauge1, 1 ether);
        vm.stopPrank();
        // some time passes so that user1's locking period ends
        vm.warp(block.timestamp + 5 weeks);
        
        // `user2` cannot change his weight although his `locked.end` is big enough
        vm.prank(user2);
        vm.expectRevert(stdError.arithmeticError);
        gc.vote_for_gauge_weights(gauge1, 0);

        // governance cannot change weight
        vm.startPrank(gov);
        vm.expectRevert(stdError.arithmeticError);
        gc.change_gauge_weight(gauge1, 2 ether);
        
        // governance cannot even remove the gauge
        // it's now impossible to do anything on gauge1
        vm.expectRevert(stdError.arithmeticError);
        gc.remove_gauge(gauge1);
        vm.stopPrank();
    }
```

## Recommendation

Perform `pt.slope -= d_slope` in `_get_weight` only when `pt.slope >= d.slope` and otherwise zero it out.

`pt.slope -= d_slope` underflow, DoS gauge operation.

This finding does a great job at describing the vulnerability and its impact from a computational point of view, including an executable PoC. Its duplicate [#386](https://github.com/code-423n4/2023-08-verwa-findings/issues/386) is also worthy of note since it explains the root cause from a mathematical point of view. Although this finding was selected as best, both findings should be read for their complementary points of view.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an integer underflow in the weight‑updating routine of a gauge controller contract that can permanently disable all operations related to a specific gauge. The root cause is that the internal function that computes the total weight for a gauge iterates over weekly checkpoints and subtracts a slope value derived from pending weight changes without first verifying that the stored slope is large enough. When governance reduces a gauge’s weight, it can set the stored bias to a lower value while leaving the slope unchanged, and later a subsequent governance increase may leave the slope at zero while the bias remains positive. If any pending weight change for a future week still has a non‑zero amount, the subtraction of that amount from a zero (or very small) slope triggers an unsigned integer underflow. This underflow occurs every time the weight‑calculation function is called, causing the function to revert and preventing any further calls that rely on it, such as voting, checkpointing, weight changes, or gauge removal. From a user’s perspective the gauge appears to be frozen: attempts to vote for the gauge, change its weight, or even remove it revert with an arithmetic error, and any funds that were delegated to the gauge cannot be withdrawn or re‑allocated, effectively locking user voting power and breaking the protocol’s incentive mechanism. The issue manifests only after a sequence where governance first lowers the gauge weight (or a malicious actor front‑runs a weight reduction) and later raises it while there remain pending weight changes for future weeks. It was discovered during a manual audit that examined the weight‑update loop and identified that the code does not guard against the slope becoming smaller than the pending change. The bug is subtle because the loop normally processes a large number of weeks and the underflow only appears under specific state transitions, making it easy to miss in routine testing. The proper fix is to ensure that the slope subtraction is performed only when the stored slope is at least as large as the pending change, otherwise the slope should be set to zero, thereby preventing the underflow and preserving the ability to interact with the gauge. This class of bug belongs to unchecked arithmetic in state‑update loops that can lead to denial‑of‑service conditions in decentralized finance contracts.
