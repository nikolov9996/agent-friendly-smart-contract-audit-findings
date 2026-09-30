---
id: 14856
severity: "High"
---

# Setting and refunding intervals enable owner theft and other problems

## Description

The setRewardsInterval function overwrites the previous reward interval when the previous interval hasn't started. This locks the rewards that were transferred in when the previous interval was set.
The storage for tracking active intervals is not correctly updated during refundRewardsInterval which allows owners to steal vault tokens and causes other problems such as:
1) Once the refunded interval starts, setRewardsInterval cannot be called until it ends.
2) Once the refunded interval ends, claimRewards for that reward token can no longer be called
3) Once setRewardsInterval() is called again after the end of the refunded interval, those funds are locked once the new interval starts because claimRewards() still reverts and there is no way to retrieve the tokens.
The setRewardsInterval function is used to set up an interval and transfer in the rewards for new campaign on a particular reward token. If there is an existing interval in progress, this function will revert.
```solidity
// A new rewards program can be set if one is not running
if (
    block.timestamp.toUint32() >= rewardsInterval.start &&
    block.timestamp.toUint32() <= rewardsInterval.end
) revert IntervalInProgress();
```
When an interval has been set but hasn't started yet, the function does not revert and proceeds to overwrite the previously set interval. Because rewards are transferred to the contract at the time the interval is set, the rewards from the previously set interval become locked in the contract.
While the refundRewardsInterval refunds the tokens, it does not update storage:
```solidity
/// @param reward The address of the reward for which campaign should be refunded
function refundRewardsInterval(address reward) payable external onlyOwner {
    if (!isReward[reward]) revert InvalidReward();
    RewardsInterval storage rewardsInterval = rewardToInterval[reward];
    if (block.timestamp >= rewardsInterval.start) revert IntervalInProgress();
    uint256 rewardsOwed = (rewardsInterval.rate * (rewardsInterval.end - rewardsInterval.start)) - 1; // Round down
    if (!POINTS_FACTORY.isPointsProgram(reward)) {
        ERC20(reward).safeTransfer(msg.sender, rewardsOwed);
    }
}
```
So this creates a situation similar to after a new interval has been set, except there are no tokens available to pay the rewards. When a new interval is not set prior to the beginning of the refunded interval, unexpected behavior ensues.
All calls to claim() for the reward token will revert when transfer is attempted in pushReward():
```solidity
function pushReward(address reward, address to, uint256 amount) internal {
    // If owed is 0, there is nothing to claim. Check allows any loop calling pushReward to continue without reversion.
    if (amount == 0) {
        return;
    }
    if (POINTS_FACTORY.isPointsProgram(reward)) {
        Points(reward).award(to, amount);
    } else {
        ERC20(reward).safeTransfer(to, amount);
    }
}
```
Calls to setRewardsInterval will revert because of this check:
```solidity
// A new rewards program can be set if one is not running
if (block.timestamp.toUint32() >= rewardsInterval.start && block.timestamp.toUint32() <= rewardsInterval.end)
    revert IntervalInProgress();
```
Once the refunded interval ends, when a new interval is created with setInterval those funds are locked because there is no way to retrieve them since claim() still reverts.
Impact: A malicious owner can take advantage of the current system:
1) Add the vault token as a reward token.
2) Set an interval on the new "reward token".
3) Allow the interval to start and pass, now there are users with unclaimed rewards.
4) Set another interval on the new "reward token" for an amount equal to the unclaimed rewards.
5) Refund that interval to get back the original amount transferred.
6) Call refund again to steal unclaimed reward tokens.

## Proof of Concept

```solidity
function testproof of conceptRefundInterval() public {
    vm.warp(block.timestamp + 50 * 52 weeks); // update timestamp

    // user deposits
    uint256 depositAmount = 1_000_000e18;
    MockERC20(address(token)).mint(REGULAR_USER, depositAmount);
    vm.startPrank(REGULAR_USER);
    token.approve(address(testIncentivizedVault), type(uint).max);
    uint256 shares = testIncentivizedVault.deposit(depositAmount, REGULAR_USER);
    vm.stopPrank();

    uint32 start = uint32(block.timestamp + 30 days);
    uint32 duration = 30 days;
    MockERC20 rewardTokena1 = rewardToken1;
    testIncentivizedVault.addRewardsToken(address(rewardTokena1));

    // set a rewards interval
    uint firstRewardsSet = 2000e18;
    rewardTokena1.mint(address(this), 5000e18);
    rewardTokena1.approve(address(testIncentivizedVault), 5000e18);
    testIncentivizedVault.setRewardsInterval(address(rewardTokena1), start, start + duration, firstRewardsSet, DEFAULT_FEE_RECIPIENT);

    vm.warp(block.timestamp + 61 days); // elapse time past the end of the interval

    // refund the interval which gets the tokens back but does not update accounting
    uint secondRewardsSet = 1000e18;
    start = start + 70 days;
    duration = 30 days;
    testIncentivizedVault.setRewardsInterval(address(rewardTokena1), start, start + duration, secondRewardsSet, DEFAULT_FEE_RECIPIENT);

    testIncentivizedVault.refundRewardsInterval(address(rewardTokena1));
    // this allows for refunding the interval again which steals the unclaimed reward tokens owed to the user
    testIncentivizedVault.refundRewardsInterval(address(rewardTokena1));
}
```

## Recommendation

Consider implementing the following changes:
• Add a line to the beginning of setRewardsInterval() that reverts if rewardToInterval[reward].start > block.timestamp -- this will prevent the reward interval from being overwritten if there is a scheduled reward interval in the future that hasn't been refunded yet.
• Add a check in addRewardsToken() which reverts if address(rewardToken) == address(VAULT).
• Update the storage to reflect the refunded interval. One idea would be to delete rewardToInterval[reward].
• But this introduces a new problem when we call setRewardsInterval() again after refunding. Since the rewardToRPT(rewardToken).lastUpdated value has previously been set to the rewardToInterval[reward].start time this will cause a panic from underflow on line #330 since rewardToInterval[reward].start has been nulled out. One solution to resolve that would be to add an early return in _calculateRewardsPerToken if rewardToInterval[reward].start == 0.
Carefully consider downstream effects from this or any solution.
Royco:
• Preventing adding vault token was added in commit 35069dfb.
• RewardToken check was added in commit 9e3227d9.
• An additional fix was added in commit 19ee0e2e

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an interval management flaw that allows the contract owner to lock and subsequently steal reward tokens. The contract uses setRewardsInterval to create a reward campaign and transfers the reward amount to the contract at the time the interval is defined. When an interval has been scheduled but has not yet started, the function does not revert and overwrites the stored interval data. Because the previously transferred tokens remain in the contract but the bookkeeping for the old interval is lost, those tokens become inaccessible to users. The refundRewardsInterval function is intended to return the unused reward tokens to the owner, but it only transfers the tokens and fails to clear or update the stored interval information. As a result the contract still believes an interval is active even after the refund, causing claimRewards to revert for that token and preventing any new interval from being created until the stale interval expires. An attacker who controls the owner role can exploit this by (1) adding a vault token as a reward, (2) setting an interval, (3) allowing the interval to pass so that users accrue unclaimed rewards, (4) setting a new interval for the same token, (5) calling refundRewardsInterval to retrieve the originally transferred amount, and (6) calling refundRewardsInterval again to capture the unclaimed rewards that remain owed to users. The impact is that users see their expected reward balance stay at zero, receive no payouts after a campaign ends, and the protocol loses funds that were supposed to be distributed. The bug manifests only when an interval is scheduled in the future and is either overwritten or refunded without proper state cleanup; it does not appear during normal operation of a single, uninterrupted interval. The affected parties are the regular users who deposit into the vault and expect rewards, as well as the protocol itself because the accounting invariants are broken. The issue was discovered during a manual security audit that examined the logic of interval creation and refund, and it is subtle because the contract does not emit explicit errors when the accounting mismatch occurs – the functions simply revert on claim, making the loss of rewards appear as a normal “no reward” condition. To remediate the problem the contract should prevent overwriting a pending interval, update or delete the interval record when a refund is performed, and disallow the vault token from being added as a reward token. Additional safeguards such as resetting internal timestamps when an interval is cleared and adding early‑return checks in reward‑per‑token calculations would close the accounting gap and restore the expected behavior that users receive their entitled rewards.
