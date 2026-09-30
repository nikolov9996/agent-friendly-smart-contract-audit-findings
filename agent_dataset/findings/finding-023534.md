---
id: 23534
severity: "High"
---

# Future epoch cache manipulation via calcAndCacheStakes allows reward manipulation

## Description

Description: The AvalancheL1Middleware::calcAndCacheStakes function lacks epoch validation, allowing attackers to cache stake values for future epochs. This enables permanent manipulation of reward calculations by locking in current stake values that may become stale by the time those epochs arrive.  

The calcAndCacheStakes function does not validate that the provided epoch is not in the future:  
```solidity
function calcAndCacheStakes(uint48 epoch, uint96 assetClassId) public returns (uint256 totalStake) {
    uint48 epochStartTs = getEpochStartTs(epoch); // No validation of epoch timing
    // ... rest of function caches values for any epoch, including future ones
}
```  

OncetotalStakeCached flag is set, any subsequent call to getOperatorStake for that epoch and asset class will return the incorrect operatorStakeCache value, as shown below:  
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

When called with a future epoch, the function queries current stake values using checkpoint systems (upper-LookupRecent) which return the latest available values for future timestamps.  

Impact: There are multiple issues with this, two major ones being:  
• Attackers can inflate their reward shares by locking in high stake values before their actual stakes decrease. All subsequent deposits/withdrawals will not impact the cached stake once it gets updated for a given epoch.  
• forceUpdateNodes mechanism can be compromised. Critical node rebalancing operations can be incorrectly skipped, leaving the system in an inconsistent state.

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

Recommended Mitigation: Consider adding epoch validation to prevent future epoch caching:  
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

The vulnerability is that the middleware function that calculates and caches stake totals does not check whether the epoch argument refers to a past or current epoch. Because of this, an attacker can call the function with a future epoch, causing the contract to store the current stake snapshot under that future epoch. Subsequent reward calculations and operator‑stake queries for that epoch read the cached value instead of the real stake at the time the epoch is processed. The root cause is the missing epoch‑validation check before caching, combined with a flag that marks the total stake as cached and makes the getter return the cached value unconditionally. An attacker can exploit this by invoking calcAndCacheStakes for a far‑future epoch while holding a large stake, then later withdrawing or reducing the stake before the epoch is reached. The cached high stake remains locked in the reward formula, inflating the attacker’s share of rewards. The impact is that reward distribution becomes inaccurate, allowing reward inflation, and node‑rebalancing logic that relies on up‑to‑date stakes may be skipped, leaving the protocol in an inconsistent state. The bug manifests when users see their expected rewards reduced or missing, while the attacker receives a larger payout; from a UI perspective a user may notice that their reward balance does not increase despite having deposited stake, or that the protocol reports higher total stakes than actually exist. The issue was discovered during a manual audit that examined the calcAndCacheStakes implementation and noticed the absence of a check against the current epoch. It is hard to notice because the function works correctly for past and current epochs, and the cached flag is only set once, so the incorrect values persist silently. The vulnerability belongs to the class of “epoch‑validation missing” or “cache poisoning” bugs, where stale data is written to a cache that is later trusted for accounting. To fix it, the contract should enforce that the supplied epoch is less than or equal to the current epoch before allowing caching, and optionally clear or forbid caching for future epochs altogether. Adding a require(epoch <= getCurrentEpoch()) prevents future‑epoch caching and ensures that reward calculations always use up‑to‑date stake data.
