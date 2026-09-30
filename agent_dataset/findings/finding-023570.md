---
id: 23570
severity: "Critical"
---

# Rewards system DOS due to unchecked asset class share and fee allocations

## Description

The REWARDS_MANAGER_ROLE can set asset class reward shares without validating that the total allocation does not exceed 100%. This enables over‑allocation of rewards, leading to potential insolvency and denial of service for later claimers.

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
- Over‑allocation: Admin sets asset class shares totaling > 100%
- In extreme case, can cause insolvency for the last batch of claimers. All rewards were claimed by earlier users leaving nothing left to claim for later user.

## Proof of Concept

Run the test in `RewardsTest.t.sol`. Note that, to demonstrate this test, the following changes were made to setup():

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
```

```solidity
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
    // DOS when 6'th operator tries to claim rewards
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

Consider adding validation in setRewardsShareForAssetClass to enforce that total share across all assets does not exceed 100%.

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

Consider adding similar validation in functions such as `updateProtocolFee`, `updateOperatorFee`, `updateCuratorFee`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unchecked allocation of reward shares for asset classes in the rewards manager. The function that sets the share for a given asset class does not verify that the sum of all asset class shares remains within the 100 % (basis points) limit. Consequently an administrator or any account holding REWARDS_MANAGER_ROLE can assign shares whose total exceeds 100 %, for example 80 % + 70 % + 50 % = 200 %. The calculation routine that distributes operator fees iterates over all asset classes, multiplies each class share by the operator’s stake proportion and adds the result to a running total. Because the total share is not bounded, the computed operatorShare can become larger than the total rewards amount. When claimOperatorFee is later called, the contract multiplies the rewards amount by this inflated operatorShare and transfers more tokens than are available in the rewards pool. The excess tokens are taken from the pool, leaving a deficit that causes later claimers to receive zero tokens or to have their claim transaction revert due to insufficient balance. The issue manifests only after rewards are distributed and operators claim their fees; individual share values appear valid in isolation, making the problem hard to notice during normal operation. The bug violates the core accounting assumption that the sum of percentage allocations must not exceed 100 %, breaking the protocol’s economic guarantees and enabling a denial‑of‑service condition for users who try to claim after the pool is exhausted. The flaw was discovered during a security audit when a test deliberately set asset class shares above 100 % and observed that total operator shares exceeded the basis‑points denominator and that the sixth operator could not claim any reward. To remediate, the contract should enforce a total‑share validation in setRewardsShareForAssetClass (and similar fee‑update functions) that aggregates the existing shares, adds the new value, and reverts if the result would exceed the basis‑points denominator. Additionally, claimOperatorFee should include a sanity check that the calculated operator reward does not exceed the available rewards amount. This class of bug is a percentage‑allocation overflow or reward‑distribution logic error that can cause funds to disappear and users to receive nothing despite expecting a payout.
