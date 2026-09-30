---
id: 21702
severity: "High"
---

# `vestTokens` bug in `MultiFeeDistribution.sol` causes new incentives to erase previous incentives

## Description

In `MultiFeeDistribution.sol`, the function `_notifyReward(address rewardToken, uint256 reward)` does not change `r.rewardPerTokenStored` and hence, relies on `_updateReward(address account)` to be called before any calls to `_notifyReward`. The rest of the functions who call `_notifyReward` follows this rule; except for `vestTokens` when it is called by a minter to give incentives to the lockers.

```solidity
function vestTokens(address user, uint256 amount, bool withPenalty) external whenNotPaused {
    if (!minters[msg.sender]) revert InsufficientPermission();
    if (amount == 0) return;

    if (user == address(this)) {
        // minting to this contract adds the new tokens as incentives for lockers
        _notifyReward(address(rdntToken), amount);
        return;
    }
    ......
}
```

Since `_updateReward` is an internal function, we also **cannot** expect minters to call it on their side before calling `vestTokens`.

Hence, this bug results in `rewardData[rewardToken].rewardPerTokenStored` being inaccurate as it will not contain the previous results accumulated by the previous `rewardData[rewardToken].rewardPerSecond` when minters call `vestTokens`. This results in all lockers losing the rewards previously accumulated by the previous `rewardPerSecond`.

## Proof of Concept

```solidity
function test_rewardsGone() public {
    assert(rewardsDuration == 30 days); // we will use 30 days as the rewardsDuration for convenience 
    address Alice = address(0x123456);
    uint256 amount = 1 ether;
    uint256[] memory lockDurations = new uint256[](1);
    uint256[] memory rewardMultipliers = new uint256[](1);
    lockDurations[0] = 700 days;
    rewardMultipliers[0] = 1;
    multiFeeDistribution.setLockTypeInfo(lockDurations, rewardMultipliers);

    stakeToken.mint(address(this), amount);
    multiFeeDistribution.setLPToken(address(stakeToken));

    multiFeeDistribution.setAddresses(IChefIncentivesController(vm.addr(uint256(keccak256("incentivesController")))), vm.addr(uint256(keccak256("treasury"))));
    vm.mockCall(
        vm.addr(uint256(keccak256("incentivesController"))),
        abi.encodeWithSelector(IChefIncentivesController.afterLockUpdate.selector, Alice),
        abi.encode(true)
    );
    stakeToken.approve(address(multiFeeDistribution), amount);
    multiFeeDistribution.stake(amount, Alice, 0);    // Alice now has 1 ether staked (with lockTypeIndex=0)
    require(multiFeeDistribution.lockedBalance(Alice) == amount);

    address[] memory minters = new address[](1);
    minters[0] = address(this);
    multiFeeDistribution.setMinters(minters);

    amount = 10000 ether;
    loopToken.mint(address(this), amount);
    loopToken.transfer(address(multiFeeDistribution), amount);

    vm.mockCall(
        mockPriceProvider,
        abi.encodeWithSelector(IPriceProvider.getRewardTokenPrice.selector, address(loopToken), amount),
        abi.encode(8)
    );
    multiFeeDistribution.vestTokens(address(multiFeeDistribution), amount, false); //Minter gives first incentives for lockers
    
    skip(31 days);
    IFeeDistribution.RewardData[] memory rewardsData = multiFeeDistribution.claimableRewards(Alice);
    require(rewardsData[0].token == address(loopToken));
    console.log("After the first incentive given   |", rewardsData[0].amount);

    amount = 1 ether;
    loopToken.mint(address(this), amount);
    loopToken.transfer(address(multiFeeDistribution), amount);
    vm.mockCall(
        mockPriceProvider,
        abi.encodeWithSelector(IPriceProvider.getRewardTokenPrice.selector, address(loopToken), amount),
        abi.encode(8)
    );
    multiFeeDistribution.vestTokens(address(multiFeeDistribution), amount, false); //Minter gives second incentives for lockers
    rewardsData = multiFeeDistribution.claimableRewards(Alice);
    require(rewardsData[0].token == address(loopToken));
    console.log("Right after second incentive given|", rewardsData[0].amount);

    skip(31 days);
    rewardsData = multiFeeDistribution.claimableRewards(Alice);
    require(rewardsData[0].token == address(loopToken));
    console.log("After everything ends             |", rewardsData[0].amount);
}
```

**Console Output:**

Ran 1 test for src/test/unit/MultiFeeDistribution.t.sol:MultiFeeDistributionTest
[PASS] test_rewardsGone() (gas: 738287)
Logs:
  After the first incentive given   | 9999999999999999999999
  Right after second incentive given| 0
  After everything ends             | 999999999999999999

Suite result: ok. 1 passed; 0 failed; 0 skipped; finished in 6.35ms (1.38ms CPU time)

Ran 1 test suite in 276.54ms (6.35ms CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)

1. (Line 21) Alice stakes 1 ether to become a locker.
2. (Line 37) Trusted minter gives out `10000 ether` as incentive to lockers by calling `vestTokens` with parameter `user == address(MultiFeeDistribution)`.
3. (Line 42) 31 days passed, calling `claimableRewards` now show that Alice has `9999999999999999999999 tokens`(`10 000 ether`) to claim. (Refer to console output).
4. (Line 53) To further reward lockers, the trusted minter further sends a 2nd incentive of `1 ether` (some time after the first incentive was given out), by again calling `vestTokens` with parameter `user == address(MultiFeeDistribution)`.
5. (Line 56) Now, calling `claimableRewards` will show that Alice has `0 tokens` to claim, proving that the previous rewards accumulated from the 1st incentive for the user has been erased.
6. (Line 61) After `rewardsDuration` for the 2nd incentive ends, we call `claimableRewards` again. We can see from the last line of the console output that only `999999999999999999 tokens`(`1 ether`) are left. Proving that Alice’s tokens from the first incentive(`10 000 ether`) has been erased, and she only retains her share of the rewards coming from the 2nd incentive(`1 ether`).

## Recommendation

```solidity
function vestTokens(address user, uint256 amount, bool withPenalty) external whenNotPaused {
    if (!minters[msg.sender]) revert InsufficientPermission();
    if (amount == 0) return;

    if (user == address(this)) {
        // minting to this contract adds the new tokens as incentives for lockers
        _updateReward(address(this));
        _notifyReward(address(rdntToken), amount);
        return;
    }
    ......
}
```

Adding `_updateReward(address(this))` will ensure `rewardData[address(rdntToken)].rewardPerTokenStored` is updated accordingly, so that lockers will not lose previously given incentives.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the MultiFeeDistribution contract's vestTokens function. When a minter calls vestTokens with the contract address as the recipient, the function directly invokes _notifyReward to add new incentive tokens but does not first update the stored reward‑per‑token value via _updateReward. The internal _notifyReward routine assumes that _updateReward has already been executed for the reward token, because elsewhere the contract calls _updateReward before _notifyReward. By skipping this step, rewardData.rewardPerTokenStored remains stale; it does not incorporate the rewardPerSecond accrued from previous incentives. Consequently, when the second incentive is added, the stale stored value overwrites the previously accumulated reward, effectively resetting the claimable amount for all lockers. Users who have previously earned rewards see their pending balance drop to zero after the second vestTokens call, even though the contract still holds the original tokens. The impact is a loss of previously earned rewards, i.e., funds disappear from the perspective of the locker owners. The bug manifests only when vestTokens is invoked with user == address(this), which is the path used by trusted minters to fund lockers. It is not triggered for regular users staking or withdrawing. The issue was uncovered during a security audit when a test case called vestTokens twice and observed that the claimableRewards for a locker went from a large amount to zero after the second call. The problem is subtle because the contract does not emit an explicit error; the reward accounting simply becomes incorrect, making it easy to miss during casual testing. The correct fix is to call _updateReward for the contract address before invoking _notifyReward, ensuring that rewardPerTokenStored is refreshed with the accumulated rewardPerSecond before new incentives are added. This class of bug belongs to the category of reward‑state‑inconsistency caused by missing state updates before modifying accounting variables, and it violates the business logic that rewards should be additive and never retroactively erased.
