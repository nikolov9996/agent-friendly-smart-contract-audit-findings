---
id: 23624
severity: "High"
---

# Immediate stake cache updates enable reward distribution without P-Chain confirmation

## Description

The middleware immediately updates stake cache for reward calculations when operators initiate stake changes via `initializeValidatorStakeUpdate()`, even though these changes remain unconfirmed by the P-Chain.  
This creates a temporal window where reward calculations diverge from the actual validated P-Chain state, potentially allowing operators to receive rewards based on unconfirmed stake increases.  

When an operator calls `initializeValidatorStakeUpdate()` to modify their validator's stake, the middleware immediately updates the stake cache for the next epoch:
// In initializeValidatorStakeUpdate():
```solidity
function _initializeValidatorStakeUpdate(address operator, bytes32 validationID, uint256 newStake)
    internal {,!
    uint48 currentEpoch = getCurrentEpoch();
    nodeStakeCache[currentEpoch + 1][validationID] = newStake;
    nodePendingUpdate[validationID] = true;
    // @audit P-Chain operation initiated but NOT confirmed
    balancerValidatorManager.initializeValidatorWeightUpdate(validationID, scaledWeight);
}
```

However, reward calculations immediately use this cached stake without verifying P-Chain confirmation:
```solidity
function getOperatorUsedStakeCachedPerEpoch(uint48 epoch, address operator, uint96 assetClass) external
    view returns (uint256) {,!
    // Uses cached stake regardless of P-Chain confirmation status
    bytes32[] memory nodesArr = this.getActiveNodesForEpoch(operator, epoch);
    for (uint256 i = 0; i < nodesArr.length; i++) {
        bytes32 nodeId = nodesArr[i];
        bytes32 validationID =
            balancerValidatorManager.registeredValidators(abi.encodePacked(uint160(uint256(nodeId))));,!
        registeredStake += getEffectiveNodeStake(epoch, validationID); // @audit Uses unconfirmed stake
    }
}
```

It is worthwhile to note that the middleware explicitly skips validators with pending updates in the `forceUpdateNodes`:
```solidity
function forceUpdateNodes(address operator, uint256 limitStake) external {
    // ...
    for (uint256 i = length; i > 0 && leftoverStake > 0;) {
        bytes32 valID =
            balancerValidatorManager.registeredValidators(abi.encodePacked(uint160(uint256(nodeId))));,!
        if (balancerValidatorManager.isValidatorPendingWeightUpdate(valID)) {
            continue; // @audit No correction possible for pending validators
        }
        // ... stake adjustment logic
    }
}
```

This creates an inconsistent approach – while rebalancing nodes, logic is verifying the P‑chain state while the same check is missing for reward estimation.

## Proof of Concept

```solidity
function test_UnconfirmedStakeImmediateRewards() public {
    // Setup: Alice has 100 ETH equivalent stake
    uint48 epoch = _calcAndWarpOneEpoch();
    // increasuing vaults total stake
    (, uint256 additionalMinted) = _deposit(staker, 500 ether);
    // Now allocate more of this deposited stake to Alice (the operator)
    uint256 totalAliceShares = mintedShares + additionalMinted;
    _setL1Limit(bob, validatorManagerAddress, assetClassId, 3000 ether, delegator);
    _setOperatorL1Shares(bob, validatorManagerAddress, assetClassId, alice, totalAliceShares,
        delegator);,!
    // Move to next epoch to make the new stake available
    epoch = _calcAndWarpOneEpoch();
    // Verify Alice now has sufficient available stake
    uint256 aliceAvailableStake = middleware.getOperatorAvailableStake(alice);
    console2.log("Alice available stake: %s ETH", aliceAvailableStake / 1 ether);
    // Alice adds a node with 10 ETH stake
    (bytes32[] memory nodeIds, bytes32[] memory validationIDs,) =
        _createAndConfirmNodes(alice, 1, 10 ether, true);
    bytes32 nodeId = nodeIds[0];
    bytes32 validationID = validationIDs[0];
    // Move to next epoch and confirm initial state
    epoch = _calcAndWarpOneEpoch();
    uint256 initialStake = middleware.getNodeStake(epoch, validationID);
    assertEq(initialStake, 10 ether, "Initial stake should be 10 ETH");
    // Alice increases stake to 1000 ETH (10x increase)
    uint256 modifiedStake = 50 ether;
    vm.prank(alice);
    middleware.initializeValidatorStakeUpdate(nodeId, modifiedStake);
    // Check: Stake cache immediately updated for next epoch (unconfirmed!)
    uint48 nextEpoch = middleware.getCurrentEpoch() + 1;
    uint256 unconfirmedStake = middleware.nodeStakeCache(nextEpoch, validationID);
    assertEq(unconfirmedStake, modifiedStake, "Unconfirmed stake should be immediately set");
    // Verify: P-Chain operation is still pending
    assertTrue(
        mockValidatorManager.isValidatorPendingWeightUpdate(validationID),
        "P-Chain operation should still be pending"
    );
    // Move to next epoch (when unconfirmed stake takes effect)
    epoch = _calcAndWarpOneEpoch();
    // Reward calculations now use unconfirmed 1000 ETH stake
    uint256 operatorStakeForRewards = middleware.getOperatorUsedStakeCachedPerEpoch(
        epoch, alice, middleware.PRIMARY_ASSET_CLASS()
    );
    assertEq(
        operatorStakeForRewards,
        modifiedStake,
        "Reward calculations should use unconfirmed 500 ETH stake"
    );
    console2.log("Stake used for rewards: %s ETH", operatorStakeForRewards / 1 ether);
}
```

## Recommendation

Consider updating the stake cache only after P-Chain confirmation rather than during initialization:
```solidity
function completeStakeUpdate(bytes32 nodeId, uint32 messageIndex) external {
    // ... existing logic ...
    // Update cache only after P-Chain confirms
    uint48 currentEpoch = getCurrentEpoch();
    nodeStakeCache[currentEpoch + 1][validationID] = validator.weight;
}
```
Note that this change also requires changes in `_calcAndCacheNodeStakeForOperatorAtEpoch` – currently the `nodeStakeCache` of current epoch is updated to the one in previous epoch, only when there are no pending updates. If the above change is implemented, `nodeStakeCache` for current epoch should always be the one rolled over from previous epochs.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a temporal inconsistency in the middleware that manages validator stake information for reward distribution. When an operator calls the function that initiates a stake change, the middleware immediately writes the new stake value into a cache that is used for the next epoch’s reward calculations, even though the underlying P‑Chain operation that actually changes the stake has not yet been confirmed. The root cause is that the cache update logic does not wait for the external confirmation and the reward‑reading function does not verify the pending‑update flag, whereas other parts of the system, such as node rebalancing, correctly skip validators with pending updates. An attacker can exploit this by submitting a stake increase, allowing the cache to reflect the inflated amount, then waiting for the epoch transition. During that epoch the reward function reads the unconfirmed cached stake and distributes rewards based on the larger, non‑final stake. This results in the operator receiving rewards that are not justified by the true, confirmed stake, effectively draining the reward pool and breaking the protocol’s accounting assumptions. The issue occurs whenever a stake update is pending on the P‑Chain and the system moves to the next epoch before confirmation, affecting validators, delegators, and the overall reward pool. It was discovered during an audit that included a unit test reproducing the scenario, showing that the cache is updated immediately and that reward calculations use the unconfirmed value. The bug is hard to notice because reward numbers appear plausible and the pending‑update flag is only consulted in other functions, not in the reward path. Conceptually, this is a race condition between state caching and external confirmation, belonging to the class of temporal inconsistency or accounting mismatch bugs. From a user’s perspective, an operator expects rewards proportional to their actual stake but may see unexpectedly high payouts, while delegators may notice reduced balances or lower-than‑expected returns. The correct mitigation is to postpone cache updates until after the P‑Chain confirms the stake change, and to ensure that reward calculations always reference confirmed stake data, thereby aligning the accounting model with the true on‑chain state.
