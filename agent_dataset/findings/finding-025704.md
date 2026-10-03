---
id: 25704
severity: "Medium"
---

# Lost rewards when the supply is 0, which always happens if the rewards are queued before anyone has StakeTracker tokens

## Description



## Proof of Concept

## Vulnerability Detail

The rewards are destributed in a [`MasterChef`](<https://medium.com/coinmonks/analysis-of-the-billion-dollar-algorithm-sushiswaps-masterchef-smart-contract-81bb4e479eb6>) style, which takes snapshots of the total accrued rewards over time and whenever someone wants to get the rewards, it subtracts the snapshot of the user from the most updated, global snapshot.

The [`rewardsPerToken()`](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/rewarders/AbstractRewarder.sol#L180>) calculation factors the blocks passed times the reward rate by the `totalSupply()`, to get the reward per token in a specific interval (and then accrues to the previous intervals, as stated in the last paragraph). When the `totalSupply()` is `0`, there is 0 `rewardPerToken()` increment as there is no supply to factor the rewards by.

The current solution is to [maintain](<https://github.com/sherlock-audit/2023-06-tokemak/blob/main/v2-core-audit-2023-07-14/src/rewarders/AbstractRewarder.sol#L176-L178>) the same `rewardsPerToken()` if the `totalSupply()` is `0`, but the `lastUpdateBlock` is still updated. This means that, during the interval in which the `totalSupply()` is `0`, no rewards are destributed but the block numbers still move forward, leaving the tokens stuck in the `MainRewarder` and `ExtraRewarder` smart contracts.

This will always happen if the rewards are quewed before the `totalSupply()` is bigger than `0` (before an initial deposit to either `DestinationVault` or `LMPVault`). It might also happen if users withdraw all their tokens from the vaults, leading to a `totalSupply()` of `0`, but this is very unlikely.

## Impact

Lost reward tokens. The amount depends on the time during which the `totalSupply()` is `0`, but could be significant.

## Code Snippet

The `rewardPerToken()` calculation:

```solidity
function rewardPerToken() public view returns (uint256) {
    uint256 total = totalSupply();
    if (total == 0) {
        return rewardPerTokenStored;
    }

    return rewardPerTokenStored + ((lastBlockRewardApplicable() - lastUpdateBlock) * rewardRate * 1e18 / total);
}
```

The `rewardPerTokenStored` does not increment when the `totalSupply()` is `0`.

## Recommendation

The `totalSupply()` should not realistically be `0` after the initial setup period (unless for some reason everyone decides to withdraw from the vaults, but this should be handled separately). It should be enough to only allow queueing rewards if the `totalSupply()` is bigger than `0`. For this, only a new check needs to be added:

```solidity
function queueNewRewards(uint256 newRewards) external onlyWhitelisted {
    if (totalSupply() == 0) revert ZeroTotalSupply();
    ...
}
```
