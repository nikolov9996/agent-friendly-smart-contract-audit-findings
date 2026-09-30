---
id: 23440
severity: "Critical"
---

# Rewards system DOS due to unchecked asset class share and fee allocations

## Description

Description: The REWARDS_MANAGER_ROLE can set asset class reward shares without validating that the total allocation does not exceed 100%. This enables over-allocation of rewards, leading to potential insolvency and denial of service for later claimers.  
A similar issue exists when assigning fee% for protocol, operator and curator. When setting each of these fees, current logic only checks that fee is less than 100% but fails to check that the cumulative fees is less than 100%.  

Rewards::setRewardsShareForAssetClass() function lacks validation to ensure total asset class shares do not exceed 100%:
```solidity
function setRewardsShareForAssetClass(uint96 assetClass, uint16 share) external
    onlyRole(REWARDS_MANAGER_ROLE) {,!
    if (share > BASIS_POINTS_DENOMINATOR) revert InvalidShare(share);
    rewardsSharePerAssetClass[assetClass] = share; // @audit No total validation
    emit RewardsShareUpdated(assetClass, share);
}
```

_calculateOperatorShare() function sums these shares without bounds checking resulting in potentially inflated numbers:
```solidity
for (uint256 i = 0; i < assetClasses.length; i++) {
    uint16 assetClassShare = rewardsSharePerAssetClass[assetClasses[i]];
    uint256 shareForClass = Math.mulDiv(operatorStake * BASIS_POINTS_DENOMINATOR / totalStake,
        assetClassShare, BASIS_POINTS_DENOMINATOR);,!
    totalShare += shareForClass; // @audit Can exceed 100%
}
```

Similarly, claimOperatorFee just assumes that the operatorShare is less than 100% which will only be true if the reward share validation exists.
```solidity
function claimOperatorFee(address rewardsToken, address recipient) external {
    // code..
    for (uint48 epoch = lastClaimedEpoch + 1; epoch < currentEpoch; epoch++) {
        uint256 operatorShare = operatorShares[epoch][msg.sender];
        if (operatorShare == 0) continue;
        // get rewards amount per token for epoch
        uint256 rewardsAmount = rewardsAmountPerTokenFromEpoch[epoch].get(rewardsToken);
        if (rewardsAmount == 0) continue;
        uint256 operatorRewards = Math.mulDiv(rewardsAmount, operatorShare,
            BASIS_POINTS_DENOMINATOR); //@audit this can exceed reward amount - no check here,!
        totalRewards += operatorRewards;
    }
}
```

Impact:
- Over-allocation: Admin sets asset class shares totaling > 100%
- In extreme case, can cause insolvency for the last batch of claimers. All rewards were claimed by earlier users leaving nothing left to claim for later user.

## Proof of Concept

```solidity
// mint only 100000 tokens instead of 1 million
rewardsToken = new ERC20Mock();
rewardsToken.mint(REWARDS_DISTRIBUTOR_ROLE, 100_000 * 10 ** 18);
vm.prank(REWARDS_DISTRIBUTOR_ROLE);
rewardsToken.approve(address(rewards), 100_000 * 10 ** 18);
// disribute only to 1 epoch instead of 10
console2.log("Setting up rewards distribution per epoch...");
uint48 startEpoch = 1;
uint48 numberOfEpochs = 1;
uint256 rewardsAmount = 100_000 * 10 ** 18;

function test_DOS_RewardShareSumGreaterThan100Pct() public {
    console2.log("=== TEST BEGINS ===");
    // 1: Modify fee structure to make operators get 100% of rewards
    // this is done just to demonstrate insolvency
    vm.startPrank(REWARDS_MANAGER_ROLE);
    rewards.updateProtocolFee(0); // 0% - no protocol fee
    rewards.updateOperatorFee(10000); // 100% - operators get everything
    rewards.updateCuratorFee(0); // 0% - no curator fee
    vm.stopPrank();
    // 2: Set asset class shares > 100%
    vm.startPrank(REWARDS_MANAGER_ROLE);
    rewards.setRewardsShareForAssetClass(1, 8000); // 80%
    rewards.setRewardsShareForAssetClass(2, 7000); // 70%
    rewards.setRewardsShareForAssetClass(3, 5000); // 50%
    // Total: 200%
    vm.stopPrank();
    // 3: Use existing working setup for stakes
    uint48 epoch = 1;
    _setupStakes(epoch, 4 hours);
    // 4: Distribute rewards
    vm.warp((epoch + 3) * middleware.EPOCH_DURATION());
    vm.prank(REWARDS_DISTRIBUTOR_ROLE);
    rewards.distributeRewards(epoch, 10);
    //5: Check operator shares (should be inflated due to 200% asset class shares)
    address[] memory operators = middleware.getAllOperators();
    uint256 totalOperatorShares = 0;
    for (uint256 i = 0; i < operators.length; i++) {
        uint256 opShare = rewards.operatorShares(epoch, operators[i]);
        totalOperatorShares += opShare;
    }
    console2.log("Total operator shares: ", totalOperatorShares);
    assertGt(totalOperatorShares, rewards.BASIS_POINTS_DENOMINATOR(),
        "VULNERABILITY: Total operator shares exceed 100%");
    //DOS when 6'th operator tries to claim rewards
    vm.warp((epoch + 1) * middleware.EPOCH_DURATION());
    for (uint256 i = 0; i < 5; i++) {
        vm.prank(operators[i]);
        rewards.claimOperatorFee(address(rewardsToken), operators[i]);
    }
    vm.expectRevert();
    vm.prank(operators[5]);
    rewards.claimOperatorFee(address(rewardsToken), operators[5]);
}
```

## Recommendation

Recommended Mitigation: Consider adding validation in setRewardsShareForAssetClass to enforce that total share across all assets does not exceed 100%.
```solidity
function setRewardsShareForAssetClass(uint96 assetClass, uint16 share) external
    onlyRole(REWARDS_MANAGER_ROLE) {,!
    if (share > BASIS_POINTS_DENOMINATOR) revert InvalidShare(share);
    // Calculate total shares including the new one
    uint96[] memory allAssetClasses = l1Middleware.getAssetClassIds();
    uint256 totalShares = share;
    for (uint256 i = 0; i < allAssetClasses.length; i++) {
        if (allAssetClasses[i] != assetClass) {
            totalShares += rewardsSharePerAssetClass[allAssetClasses[i]];
        }
    }
    if (totalShares > BASIS_POINTS_DENOMINATOR) {
        revert TotalAssetClassSharesExceed100Percent(totalShares); //@audit this check ensures proper
        distribution,!
    }
    rewardsSharePerAssetClass[assetClass] = share;
    emit RewardsShareUpdated(assetClass, share);
}
```
Consider adding similar validation in functions such as updateProtocolFee, updateOperatorFee, updateCuratorFee.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unchecked cumulative allocation bug in the rewards distribution system. The contract permits the REWARDS_MANAGER_ROLE to set reward shares for individual asset classes and to configure protocol, operator and curator fees without verifying that the sum of all shares or fees stays within the 100 % (basis‑points) limit. Because setRewardsShareForAssetClass only checks that a single share is ≤ BASIS_POINTS_DENOMINATOR and the fee‑update functions perform the same single‑value check, an administrator can configure multiple asset classes whose shares add up to more than 100 %, or set fees whose combined percentage exceeds the total pool. When rewards are later calculated, the _calculateOperatorShare routine iterates over all asset classes, multiplies each share by the operator’s stake proportion, and aggregates the results into totalShare. Without a bound check, totalShare can exceed the denominator, causing operatorRewards computed in claimOperatorFee to be larger than the actual rewards amount. The contract then attempts to transfer more tokens than are available, which either reverts or leaves later claimers with zero balance. This leads to over‑allocation of rewards, insolvency of the reward pool, and a denial‑of‑service condition for users who try to claim after the pool is exhausted. The issue occurs whenever multiple asset classes are active and the manager sets shares without total validation, especially when combined with high operator fee settings. It affects operators, later claimers, and the overall protocol economics because the accounting assumptions that total allocated shares must not exceed 100 % are violated. The flaw was discovered during a security audit and reproduced with a unit test that deliberately set asset class shares to 80 %, 70 % and 50 % (total 200 %) and set the operator fee to 100 %, demonstrating that the total operator shares exceed the basis‑points denominator and that the sixth operator’s claim fails. The problem is hard to notice because each individual share appears valid and the contract emits no warning when the cumulative total is too high. The recommended fix is to add a validation step in setRewardsShareForAssetClass (and analogous fee‑update functions) that computes the sum of all existing shares plus the new value and reverts if the total exceeds BASIS_POINTS_DENOMINATOR, thereby enforcing the invariant that total allocated percentages never surpass 100 % and preventing reward pool insolvency.
