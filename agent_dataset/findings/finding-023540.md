---
id: 23540
severity: "High"
---

# Immediate stake cache updates enable reward distribution without P-Chain confirmation

## Description

Description: The middleware immediately updates stake cache for reward calculations when operators initiate stake changes via `initializeValidatorStakeUpdate()`, even though these changes remain unconfirmed by the P-Chain.  
This creates a temporal window where reward calculations diverge from the actual validated P-Chain state, potentially allowing operators to receive rewards based on unconfirmed stake increases.  

When an operator calls `initializeValidatorStakeUpdate()` to modify their validator's stake, the middleware immediately updates the stake cache for the next epoch:  

```solidity
// In initializeValidatorStakeUpdate():
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

The middleware explicitly skips validators with pending updates in the `forceUpdateNodes` function:  

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

This creates an inconsistent approach – while rebalancing nodes, logic verifies the P-chain state, but the same check is missing for reward estimation.

## Proof of Concept

Current POC shows that the reward calculation uses unconfirmed stake updates. Add to `AvalancheMiddlewareTest.t.sol`  

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

Recommended Mitigation: Consider updating the stake cache only after P-Chain confirmation rather than during initialization:  

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

The vulnerability is an immediate stake‑cache update bug that allows reward distribution to be based on unconfirmed stake changes. When an operator calls the stake‑update entry point, the middleware writes the requested new stake into its nodeStakeCache for the next epoch before the asynchronous P‑Chain transaction that actually changes the validator’s weight has been confirmed. The reward calculation function later reads this cached value without verifying the confirmation status, so it attributes a larger effective stake to the operator. This creates a temporal window where the accounting used for rewards diverges from the true state on the P‑Chain. An operator can therefore receive a reward boost in the epoch following the stake‑update call, even if the P‑Chain later rejects the update or takes multiple epochs to confirm it. The impact is that operators may earn rewards that are not backed by real stake, draining the reward pool and breaking the economic assumptions of the protocol. The issue occurs only for validators with a pending weight‑update; validators without pending updates are unaffected. It was discovered during a security audit by inspecting the middleware’s initializeValidatorStakeUpdate function and observing that nodeStakeCache is set immediately, and then confirming through a test that getOperatorUsedStakeCachedPerEpoch returns the unconfirmed stake. The bug is subtle because the rebalancing logic in forceUpdateNodes correctly skips pending validators, giving the impression that pending updates are handled consistently, while the reward path lacks this guard. From a user’s perspective the UI may show a higher reward or a larger balance after a stake increase, contradicting the expectation that rewards correspond to confirmed stake. The class of bug is a state‑synchronisation flaw between off‑chain cache and on‑chain source of truth, specifically a premature cache write leading to accounting inconsistency. The recommended fix is to defer updating nodeStakeCache until after the P‑Chain confirms the weight change, for example by moving the cache write into a completion callback such as completeStakeUpdate, and ensuring that the cache for the current epoch always reflects the rolled‑over value from the previous epoch regardless of pending updates. This aligns reward calculations with the verified validator state and eliminates the reward‑inflation attack vector.
