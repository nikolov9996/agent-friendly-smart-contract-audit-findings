---
id: 15909
severity: "High"
---

# Future stakers are paid with rewards that have been accrued from the past due to miscalculation in userRewardPerTokenPaid and _perTokenReward.

## Description

```solidity
    modifier updateReward(address account, uint256 index) {
        {
            // stack too deep
            rewardData.rewardPerTokenStored = uint216(_rewardPerToken());
            rewardData.lastUpdateTime = uint40(_lastTimeRewardApplicable(rewardData.periodFinish));
            if (_account != address(0)) {
                StakeInfo memory stakeInfo = stakeInfos[account][index];
                uint256 vestingRate = getVestingRate(stakeInfo);
                claimableRewards[account][index] = earned(stakeInfo, account, index);
                userRewardPerTokenPaid[account][index] = vestingRate * uint256(rewardData.rewardPerTokenStored) / 1e18;
            }
        }
        _;
    }
```
```solidity
    function getVestingRate(StakeInfo memory stakeInfo) internal view returns (uint256 vestingRate) {
        if (_stakeInfo.stakeTime == 0) {
            return 0;
        }
        if (block.timestamp > _stakeInfo.fullyVestedAt) {
            vestingRate = 1e18;
        } else {
            vestingRate = (block.timestamp - _stakeInfo.stakeTime) * 1e18 / vestingPeriod;
        }
    }
```
Future stakers are always vested rewards using the total rewardPerToken without deducting how much rewardPerToken has already been accumulated before they stake.

Any new staker will be rewarded with rewardData.rewardPerTokenStored that have been accumulated since creation of contract. That means a user who hasn't been staking from the beginning will be rewarded the same as a user who has been staking since the beginning. Or in other words the contract assumes that every user staked when the rewardData.rewardPerTokenStored is 0.

This is exactly the same problem mentioned here by rareskills.

stake calls updateReward modifier and we can see that every new staker's userRewardPerTokenPaid will be 0 since vesting rate is currently 0;

Suppose, after 1 year the accumulated rewardPerTokenStored is 1000e18, which means every token staked since the beginning has earned 1000 tokens each. A new user Bob stakes 100 TEMPLE tokens. Assuming the vesting period is 16 weeks, Bob claims his rewards after 16 weeks. Now his reward calculation is;

```solidity
        return  
            (stakeInfo.amount * (perTokenReward - userRewardPerTokenPaid[account][index])) / 1e18 +
            claimableRewards[account][index];
```

(100 TEMPLE * (1000e18 - 0)) / 1e18 + 0 = 100,000 TGLD rewards for staking 16 weeks.

This is assuming no new rewards are added, where Bob should've gotten 0 TGLD as rewards. Bob just earned rewards equivalent to staking 1 year + 16 weeks (for new rewards).

The issue here is that the contract does not account for the already accumulated rewardPerTokenStored from the past when calculating the new staker's userRewardPerTokenPaid and calculates it using the total rewardPerToken: userRewardPerTokenPaid[account][index] = vestingRate * uint256(rewardData.rewardPerTokenStored) / 1e18.

Loss of reward tokens and unfair reward calculation for initial stakers or DOS (not enough reward tokens). It also opens an attack path where a user can steal unclaimed rewards even when there are no new rewards added i.e. a user who enters after no new rewards are distributed will still get rewards from the past.

## Proof of Concept

no poc

## Recommendation

```solidity
    //@audit a new variable to keep track of the already accumulated rewardPerToken before the user enters the protocol
    mapping(address account => mapping(uint256 index => uint256 amount)) public userRewardDebt; 
```
note that we cannot use the variable userRewardPerTokenPaid to track the already accumulated rewardPerToken because of the vestingRate, that would introduce another problem.
```diff
    function stakeFor(address for, uint256 amount) public whenNotPaused {
        if (_amount == 0) revert CommonEventsAndErrors.ExpectedNonZero();

        stakingToken.safeTransferFrom(msg.sender, address(this), _amount);
        uint256 lastIndex = accountLastStakeIndex[_for];
        accountLastStakeIndex[for] = ++_lastIndex; 
userRewardDebt[for][lastIndex] = rewardPerToken(); //@audit we need to make sure we do it here before applyStake, because it calls updateReward 

        applyStake(for, amount, lastIndex); 
        moveDelegates(address(0), delegates[for], _amount);
    }
```
```diff
    modifier updateReward(address account, uint256 index) {
        {
            // stack too deep
            rewardData.rewardPerTokenStored = uint216(_rewardPerToken());
            rewardData.lastUpdateTime = uint40(_lastTimeRewardApplicable(rewardData.periodFinish));
            if (_account != address(0)) {
                StakeInfo memory stakeInfo = stakeInfos[account][index];
                uint256 vestingRate = getVestingRate(stakeInfo);
                claimableRewards[account][index] = earned(stakeInfo, account, index);
userRewardPerTokenPaid[account][index] = vestingRate * uint256(rewardData.rewardPerTokenStored) / 1e18;
//@audit vest only the newly accrued rewardPerToken after the user enters 
userRewardPerTokenPaid[account][index] = vestingRate * (uint256(rewardData.rewardPerTokenStored) - userRewardDebt[account][index] ) / 1e18;
                // this will still be zero when new staker enters, but since we deduct the userRewardDebt before calculating it, we will only reward with the newly accrued rewardPerToken
            }
        }
        _;
    }
```
```diff
    function _earned(
        StakeInfo memory _stakeInfo,
        address _account,
        uint256 _index
    ) internal view returns (uint256) {
        uint256 vestingRate = getVestingRate(stakeInfo);
        if (vestingRate == 0) {
            return 0;
        }
        uint256 _perTokenReward;
        if (vestingRate == 1e18) { 
perTokenReward = rewardPerToken();
perTokenReward = rewardPerToken() - userRewardDebt[account][index];
        } else { 
perTokenReward = rewardPerToken() * vestingRate / 1e18;
perTokenReward = (rewardPerToken() - userRewardDebt[account][index]) * vestingRate / 1e18;
        }
        
        return
            (stakeInfo.amount * (perTokenReward - userRewardPerTokenPaid[account][index])) / 1e18 +
            claimableRewards[account][index];
    }
```
This ensures that _perTokenReward for the staker is only the newly accumulated rewardPerToken, post staking.

Medium Risk Findings

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract contains a reward‑distribution miscalculation that allows users who join the staking pool after rewards have already accumulated to claim the full historical reward per token instead of only the rewards that accrue after they stake. The root cause is that the updateReward modifier records userRewardPerTokenPaid as vestingRate * rewardData.rewardPerTokenStored / 1e18 without subtracting the portion of rewardPerToken that was generated before the user entered the protocol. Consequently, for a new staker the vestingRate is initially zero, so userRewardPerTokenPaid is set to zero, and the earned function later computes rewards as (stakeAmount * (perTokenReward - 0)) / 1e18 plus any previously claimable amount. Because perTokenReward reflects the total rewardPerToken stored since contract deployment, the new staker receives rewards that correspond to the entire history of the pool, even if no new rewards were added after their deposit. An attacker can exploit this by staking a small amount after a long reward‑accumulation period, waiting for the vesting period to finish, and then claiming an outsized amount of reward tokens that were never intended for them. The impact is a massive over‑allocation of reward tokens, effectively draining the reward reserve, unfairly rewarding late participants, and potentially causing a denial‑of‑service condition for legitimate early stakers who will find the pool empty. The vulnerability manifests whenever a user stakes after the contract’s rewardPerToken has become non‑zero, which is any time after the first reward distribution. All participants in the staking protocol—both early and late stakers, as well as the protocol’s treasury—are affected because the accounting assumptions that rewards are earned only after a stake are violated. The issue was discovered during a manual audit that compared the reward accounting logic with the intended vesting model and identified that the contract assumes every user started staking when rewardPerToken was zero. It is subtle because the contract still updates claimableRewards and appears to respect vesting rates, so the over‑payment is not obvious from a superficial inspection or from normal UI output; users simply see a large reward balance after claiming, which may be interpreted as a bonus rather than a bug. The bug belongs to the class of “reward‑per‑token accounting errors” or “incorrect reward debt handling” where the reward debt (the amount of reward per token already accounted for) is not recorded for new participants. To fix the issue, the contract should store a snapshot of the current rewardPerToken at the moment a user stakes (often called rewardDebt or userRewardDebt) and subtract this snapshot from future per‑token calculations, ensuring that only newly accrued rewards are credited to the staker. This adjustment aligns the reward calculation with the intended business logic that rewards accrue only after a stake, restores fairness, and prevents the protocol from unintentionally distributing historic rewards to newcomers.
