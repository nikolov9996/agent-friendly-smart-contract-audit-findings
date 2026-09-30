---
id: 23577
severity: "High"
---

# Future epochcache manipulation via calcAndCacheStakes allows reward manipulation

## Description

The AvalancheL1Middleware::calcAndCacheStakes function lacks epoch validation, allowing attackers to cache stake values for future epochs. This enables permanent manipulation of reward calculations by locking in current stake values that may become stale by the time those epochs arrive.  

The `calcAndCacheStakes` function does not validate that the provided epoch is not in the future:

```solidity
function calcAndCacheStakes(uint48 epoch, uint96 assetClassId) public returns (uint256 totalStake) {
    uint48 epochStartTs = getEpochStartTs(epoch); // No validation of epoch timing
    // ... rest of function caches values for any epoch, including future ones
}
```

When `totalStakeCached` flag is set, any subsequent call to `getOperatorStake` for that epoch and asset class will return the incorrect `operatorStakeCache` value:

```solidity
function getOperatorStake(
    address operator,
    uint48 epoch,
    uint96 assetClassId
) public view returns (uint256 stake) {
    if (totalStakeCached[epoch][assetClassId]) {
        uint256 cachedStake = operatorStakeCache[epoch][assetClassId][operator];
        return cachedStake;
    }
    ...
}
```

When called with a future epoch, the function queries current stake values using checkpoint systems (`upper-LookupRecent`) which return the latest available values for future timestamps.  

Impact:  
- Attackers can inflate their reward shares by locking in high stake values before their actual stakes decrease. All subsequent deposits/withdrawals will not impact the cached stake once it gets updated for a given epoch.  
- `forceUpdateNodes` mechanism can be compromised. Critical node rebalancing operations can be incorrectly skipped, leaving the system in an inconsistent state.

## Proof of Concept

Add the following test and run it:

```solidity
function test_operatorStakeOfTwoEpochsShouldBeEqual() public {
    uint256 operatorStake = middleware.getOperatorStake(alice, 1, assetClassId);
    console2.log("Operator stake (epoch", 1, "):", operatorStake);
    middleware.calcAndCacheStakes(5, assetClassId);
    uint256 newStake = middleware.getOperatorStake(alice, 2, assetClassId);
    console2.log("New epoch operator stake:", newStake);
    assertGe(newStake, operatorStake);
    uint256 depositAmount = 100_000_000_000_000_000_000;
    collateral.transfer(staker, depositAmount);
    vm.startPrank(staker);
    collateral.approve(address(vault), depositAmount);
    vault.deposit(staker, depositAmount);
    vm.stopPrank();
    vm.warp((5) * middleware.EPOCH_DURATION());
    middleware.calcAndCacheStakes(5, assetClassId);
    assertEq(
        middleware.getOperatorStake(alice, 4, assetClassId), middleware.getOperatorStake(alice, 5,
        assetClassId),!
    );
}
```

## Recommendation

Consider adding epoch validation to prevent future epoch caching:

```solidity
function calcAndCacheStakes(uint48 epoch, uint96 assetClassId) public returns (uint256 totalStake) {
    uint48 currentEpoch = getCurrentEpoch();
    require(epoch <= currentEpoch, "Cannot cache future epochs"); //@audit added
    uint48 epochStartTs = getEpochStartTs(epoch);
    // ... rest of function unchanged
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a future‑epoch stake caching flaw in the AvalancheL1Middleware contract. The function calcAndCacheStakes accepts an epoch identifier but does not verify that the epoch is not in the future, allowing any caller to store the current stake snapshot for an epoch that has not yet occurred. Because the contract later reads the cached value in getOperatorStake whenever the totalStakeCached flag is set, reward calculations for that epoch rely on a stale total stake that does not reflect later deposits, withdrawals, or stake reductions. An attacker can exploit this by invoking calcAndCacheStakes with a future epoch while holding a large stake, thereby locking in an inflated totalStake value. When the epoch arrives, the cached operatorStakeCache is used, causing the attacker’s share of rewards to be calculated against an artificially high total, inflating their reward portion. Subsequent legitimate actions by other users, such as deposits or withdrawals, do not modify the cached snapshot, so the reward distribution remains skewed. This manipulation also interferes with the forceUpdateNodes mechanism, which may skip necessary node rebalancing because it believes the cached stake already satisfies balance conditions, leaving the system in an inconsistent state. The issue is discovered during a security audit that examined the epoch handling logic and observed that no check against the current epoch existed. It can be hard to notice because the contract still returns plausible stake numbers, and the UI may show expected balances while the underlying reward accounting is wrong. The impact includes potential over‑allocation of rewards to malicious actors, reduced rewards for honest participants, and possible network instability due to missed rebalancing. The bug belongs to the class of time‑based state‑caching errors where future timestamps are accepted without validation, breaking accounting assumptions that stake totals evolve only with actual epoch progression. To fix the issue, the function should retrieve the current epoch and require that the supplied epoch be less than or equal to it before performing any caching, thereby preventing future‑epoch manipulation and ensuring that reward calculations always use up‑to‑date stake data.
