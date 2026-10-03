---
id: 25159
severity: "Medium"
---

# Precision Loss in notifyRewardAmount Function Causes Unclaimable RewardToken

## Description



## Proof of Concept

## Vulnerability Detail

In the `StakedEXA` contract, there is a precision loss in the `notifyRewardAmount` function when calculating `rewardData.rate`, which results in some of the reward funds being locked in the contract and not being available for distribution. This leads to economic loss.

```solidity
function notifyRewardAmount(IERC20 reward, uint256 amount, address notifier) internal onlyReward(reward) {
    updateIndex(reward);
    RewardData storage rewardData = rewards[reward];
    if (block.timestamp >= rewardData.finishAt) {
      rewardData.rate = amount / rewardData.duration;
    } else {
      uint256 remainingRewards = (rewardData.finishAt - block.timestamp) * rewardData.rate;
      rewardData.rate = (amount + remainingRewards) / rewardData.duration;
    }

    if (rewardData.rate == 0) revert ZeroRate();
    if (
      rewardData.rate * rewardData.duration >
      reward.balanceOf(address(this)) - (address(reward) == asset() ? totalAssets() : 0)
    ) revert InsufficientBalance();

    rewardData.finishAt = uint40(block.timestamp) + rewardData.duration;
    rewardData.updatedAt = uint40(block.timestamp);

    emit RewardAmountNotified(reward, notifier, amount);
  }
```

Clearly, the formulas `rewardData.rate = amount / rewardData.duration;` and `rewardData.rate = (amount + remainingRewards) / rewardData.duration;` in the calculation of `rewardData.rate` cause precision loss. This results in the final reward amount `rewardData.rate * rewardData.duration` being less than the `amount` actually passed to the `notifyRewardAmount` function. Since there is no suitable function to extract this remaining portion of funds, it causes economic loss.

A Proof of Concept (POC) can be constructed in `StakedEXA.t.sol` as follows.

```solidity
function testRemaining() external {
    MockERC20 WBTC = new MockERC20("Wrapped BTC", "WBTC", 8);
    vm.label(address(WBTC), "WBTC");
    WBTC.mint(address(stEXA), 10e8);
    stEXA.enableReward(WBTC);
    stEXA.setRewardsDuration(WBTC, 1 weeks);
    stEXA.notifyRewardAmount(WBTC, 10e8);

    address Alice = address(0x1234);
    vm.startPrank(Alice);
    exa.mint(address(Alice), 1 ether);
    exa.approve(address(stEXA), 1 ether);
    stEXA.deposit(1 ether, Alice);

    skip(30 weeks);

    stEXA.claim(WBTC);

    emit log_named_decimal_uint("balance", WBTC.balanceOf(address(stEXA)), WBTC.decimals());
    emit log_named_decimal_uint("Alice reward WBTC", WBTC.balanceOf(Alice), WBTC.decimals());
    emit log_named_decimal_uint("saving WBTC", WBTC.balanceOf(SAVINGS), WBTC.decimals());
}
```

The output is as follows:

```sh
Logs:
  balance: 0.00265600
  Alice reward WBTC: 8.99760960
  saving WBTC: 0.99973440
```

Assuming WBTC as the reward token with an amount of 10 and `RewardsDuration` set to one week, and Alice as the only staker with a stake of 1 ether worth of EXA tokens. After 30 weeks, based on the set parameters, the reward distribution should be complete. When Alice calls the `claim` function, the full 10 ether worth of rewards should be distributed to Alice and savings. However, due to precision loss, 0.0026 WBTC will remain in the contract (worth over 100 USD).

## Impact

The precision loss in the `StakedEXA` contract's `notifyRewardAmount` function results in a portion of the reward funds being locked in the contract and unavailable for distribution.

## Code Snippet

[https://github.com/sherlock-audit/2024-07-exactly-stacking-contracts/blob/main/protocol/contracts/StakedEXA.sol#L209-L229](<https://github.com/sherlock-audit/2024-07-exactly-stacking-contracts/blob/main/protocol/contracts/StakedEXA.sol#L209-L229>)

## Recommendation

Add an admin function to extract the reward tokens that remain undistributed due to precision loss.
