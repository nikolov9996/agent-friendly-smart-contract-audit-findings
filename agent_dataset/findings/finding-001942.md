---
id: 1942
severity: "High"
---

# _requestedTip is not deduced

## Description

Description
GovernanceStaker introduces the concept of bumping earning power to control the amount of rewards claimable by depositors who delegate to inactive delegatees. The bumpEarningPower function enables keepers to update earningPower on behalf of depositors, and take a fee to do so.
GovernanceStaker.sol#L508:
```solidity
// Send tip to the receiver
SafeERC20.safeTransfer(REWARD_TOKEN, _tipReceiver, _requestedTip);
```
Some checks are done to ensure that depositor has enough rewards so that the _requestedTip can be covered out of the rewards.
GovernanceStaker.sol#L489-L497:
```solidity
if (_newEarningPower > deposit.earningPower && _unclaimedRewards < _requestedTip) {
    revert GovernanceStaker__InsufficientUnclaimedRewards();
}
```
tip is more than unclaimed rewards
```solidity
if (_newEarningPower < deposit.earningPower && (_unclaimedRewards - _requestedTip) < maxBumpTip) {
    revert GovernanceStaker__InsufficientUnclaimedRewards();
}
```
Unfortunately, the requested tip is never deducted from the depositor rewards. Which means that the accounting is incorrect, and some legitimate participants would not be able to claim their rewards.
Rewards are denied to legitimate participants (rewards insolvency)

## Proof of Concept

no poc

## Recommendation

Consider subtracting the tip from the depositor rewards:
GovernanceStaker.sol#L508:
```solidity
// Send tip to the receiver
SafeERC20.safeTransfer(REWARD_TOKEN, _tipReceiver, _requestedTip);
+
deposit.scaledUnclaimedRewardCheckpoint =
+
deposit.scaledUnclaimedRewardCheckpoint - (_requestedTip * SCALE_FACTOR);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting omission in the GovernanceStaker contract where the bumpEarningPower function transfers a tip to a designated receiver but never deducts the requested tip amount from the depositor's unclaimed reward balance. The root cause is a missing state update after the SafeERC20.safeTransfer call; the contract checks that the depositor has sufficient unclaimed rewards to cover the tip, yet it does not adjust deposit.scaledUnclaimedRewardCheckpoint (or the equivalent reward accounting variable) to reflect the transferred tip. An attacker, typically a keeper, can exploit this by invoking bumpEarningPower with a non‑zero tip; the tip is sent out of the contract while the depositor’s internal reward counter remains unchanged, allowing the same rewards to be claimed later by the depositor or to be repeatedly siphoned by successive tip payments. Over time this leads to rewards insolvency: legitimate participants who have delegated to inactive delegatees may find that their expected rewards are unavailable, claim transactions revert with insufficient rewards, or the claimed amount is lower than displayed in the UI. The issue manifests whenever bumpEarningPower is called with a tip that passes the pre‑condition checks, affecting any depositor whose earnings are being bumped and any keeper who can trigger the function. It was discovered during a manual audit by Sherlock, who noted that the tip transfer succeeded but the accounting variable was never updated, a subtle bug that can be missed because external balances appear correct while internal bookkeeping diverges. The problem is hard to notice because the contract does not emit an explicit error; users only see a mismatch between the displayed reward balance and the amount they can actually claim. To remediate, the contract should subtract the tip from the depositor’s scaled unclaimed reward checkpoint (or the appropriate reward state) immediately after the transfer, ensuring that the total rewards pool remains consistent with the sum of individual balances. This class of bug falls under missing state mutation after an external token transfer, leading to double‑spending of reward tokens and violating the protocol’s accounting invariants that each depositor’s claimable amount must never exceed the total rewards allocated to them. From the user’s perspective, the UI may show a positive reward amount, the user expects to receive that amount, but the transaction either returns zero or a smaller amount, effectively causing funds to disappear or refunds to be missing.
