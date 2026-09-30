---
id: 22516
severity: "High"
---

# Heap is incorrectly storing the removed operator

## Description

An operator's strategy can be reset by the owner calling setOperatorStrategyCaps to "0". This action sets the utilization to "0" and removes the operator from the heap. Consequently, this means that the operator has unwound all its strategy shares and can no longer receive any more deposits. However, due to how the heap is organized, if an operator who had funds before is reset to "0", the heap will not successfully remove the operator. As a result, when ordering the heap, a division by "0" will occur, causing the transaction to revert on deposits and withdrawals indefinitely.

In order to break down the issue, let's divide the issue into 2 parts which their combination is the issue itself.

1- Heap is not removing the removed ID from the heap's storage when the operator is removed.

When the operator is removed, the operator will be removed from the heap as follows:
```solidity
function setOperatorStrategyCap(
    RioLRTOperatorRegistryStorageV1.StorageV1 storage s,
    uint8 operatorId,
    IRioLRTOperatorRegistry.StrategyShareCap memory newShareCap
) internal {
    OperatorUtilizationHeap.Data memory utilizationHeap = s.getOperatorUtilizationHeapForStrategy(newShareCap.strategy);

    // If the current cap is greater than 0 and the new cap is 0, remove the operator from the strategy.
    if (currentShareDetails.cap > 0 && newShareCap.cap == 0) {
        // If the operator has allocations, queue them for exit.
        if (currentShareDetails.allocation > 0) {
            operatorDetails.queueOperatorStrategyExit(operatorId, newShareCap.strategy);
        }
        // Remove the operator from the utilization heap.
        utilizationHeap.removeByID(operatorId);
    }

    // Persist the updated heap to the active operators tracking.
    utilizationHeap.store(s.activeOperatorsByStrategyShareUtilization[newShareCap.strategy]);
}
```
removeByID calls the internal _remove function which does NOT remove the last element! self.count is decreased however, the index is still the previous value of the self.count.
```solidity
function _remove(Data memory self, uint8 i) internal pure {
    self.operators[i] = self.operators[self.count--];
}
```
For example, if there are 3 operators as follows: operatorId: 1, utilization: 50% operatorId: 2, utilization: 60% operatorId: 3, utilization: 70% then, the heap.count would be 3 and the order would be: 1, 2, 3 in the heap heap.operators[1] = operatorId 1 heap.operators[2] = operatorId 2 heap.operators[3] = operatorId 3

If we remove the operator Id 2: heap.count = 2 order: 1,3 heap.operators[1] = operatorId 1 heap.operators[2] = operatorId 2 heap.operators[3] = operatorId 0

THIS SHOULD BE "0" since it's removed but it is "3" in the current implementation!

As shown here, the operators[3] should be "0" since there isn't any operator3 in the heap anymore but the heap keeps the value and does not reset it.

Here a test shows the above issue:
```solidity
// forge test --match-contract OperatorUtilizationHeapTest --match-test test_removingDoesNotUpdatesStoredHeap -vv
function test_removingDoesNotUpdatesStoredHeap() public {
    OperatorUtilizationHeap.Data memory heap = OperatorUtilizationHeap.initialize(5);

    heap.insert(OperatorUtilizationHeap.Operator({id: 1, utilization: 50}));
    heap.store(heapStore);
    heap.insert(OperatorUtilizationHeap.Operator({id: 2, utilization: 60}));
    heap.store(heapStore);
    heap.insert(OperatorUtilizationHeap.Operator({id: 3, utilization: 70}));
    heap.store(heapStore);
    console.log("Heaps count", heap.count);
    console.log("1st", heap.operators[1].id);
    console.log("2nd", heap.operators[2].id);
    console.log("3rd", heap.operators[3].id);
    // remove 2
    heap.removeByID(3);
    heap.store(heapStore);
    console.log("Heaps count", heap.count);
    console.log("1st", heap.operators[1].id);
    console.log("2nd", heap.operators[2].id);
    console.log("3rd", heap.operators[3].id);
}
```
Logs:

2- When the operator cap is reset the allocations/deallocations will not work due to above heap issue because of division by zero.

Now, take the above example, we removed the operatorId 3 from the heap by setting its cap to "0". Now, there are only operators 1 and 2 active for that specific strategy. When there are idle funds in the deposit pool before the rebalance call, the excess funds that are not requested as withdrawals will be pushed to EigenLayer as follows:
```solidity
function rebalance(address asset) external checkRebalanceDelayMet(asset) {
    (uint256 sharesReceived, bool isDepositCapped) = depositPool().depositBalanceIntoEigenLayer(asset);
}
```
```solidity
function depositBalanceIntoEigenLayer(address asset) external onlyCoordinator returns (uint256, bool) {
    uint256 amountToDeposit = asset.getSelfBalance();
    if (amountToDeposit == 0) return (0, false);

    address strategy = assetRegistry().getAssetStrategy(asset);
    uint256 sharesToAllocate = assetRegistry().convertToSharesFromAsset(asset, amountToDeposit);

    return (OperatorOperations.depositTokenToOperators(operatorRegistry(), asset, strategy, sharesToAllocate), isDepositCapped);
}
```
```solidity
function depositTokenToOperators(
    IRioLRTOperatorRegistry operatorRegistry,
    address token,
    address strategy,
    uint256 sharesToAllocate
) internal returns (uint256 sharesReceived) {
    (uint256 sharesAllocated,
     IRioLRTOperatorRegistry.OperatorStrategyAllocation[] memory allocations) =
        operatorRegistry.allocateStrategyShares(
            strategy, sharesToAllocate
        );

    for (uint256 i = 0; i < allocations.length; ++i) {
        IRioLRTOperatorRegistry.OperatorStrategyAllocation memory allocation = allocations[i];

        IERC20(token).safeTransfer(allocation.delegator, allocation.tokens);
        sharesReceived += IRioLRTOperatorDelegator(allocation.delegator).stakeERC20(strategy, token, allocation.tokens);
    }

    if (sharesReceived != sharesAllocated) revert INCORRECT_NUMBER_OF_SHARES_RECEIVED();
}
```
```solidity
function allocateStrategyShares(address strategy, uint256 sharesToAllocate) external onlyDepositPool returns (uint256 sharesAllocated, OperatorStrategyAllocation[] memory allocations) {
    OperatorUtilizationHeap.Data memory heap = s.getOperatorUtilizationHeapForStrategy(strategy);
}
```
```solidity
function getOperatorUtilizationHeapForStrategy(RioLRTOperatorRegistryStorageV1.StorageV1 storage s, address strategy) internal view returns (OperatorUtilizationHeap.Data memory heap) {
    uint8 numActiveOperators = s.activeOperatorCount;
    if (numActiveOperators == 0) return OperatorUtilizationHeap.Data(new OperatorUtilizationHeap.Operator[](0), 0);

    heap = OperatorUtilizationHeap.initialize(MAX_ACTIVE_OPERATOR_COUNT);
    LibMap.Uint8Map storage operators = s.activeOperatorsByStrategyShareUtilization[strategy];

    IRioLRTOperatorRegistry.OperatorShareDetails memory operatorShares;
    unchecked {
        uint8 i;
        for (i = 0; i < numActiveOperators; ++i) {
            uint8 operatorId = operators.get(i);
            // Non-existent operator ID. We've reached the end of the heap.
            if (operatorId == 0) break;
            operatorShares = s.operatorDetails[operatorId].shareDetails[strategy];

            heap.operators[i + 1] = OperatorUtilizationHeap.Operator({
                id: operatorId,
                utilization: operatorShares.allocation.divWad(operatorShares.cap)
            });
        }
        heap.count = i;
    }
}
```
As we can see in one above code snippet, the numActiveOperators is 3. Since the stored heap's last element is not set to "0" it will point to operatorId 3 which has a cap of "0" after the removal. This will make the utilization: operatorShares.allocation.divWad(operatorShares.cap) part of the code to perform a division by zero and the function will revert.

Coded PoC:
```solidity
// forge test --match-contract RioLRTOperatorRegistryTest --match-test test_Capped0ValidatorBricksFlow -vv
function test_Capped0ValidatorBricksFlow() public {
    // Add 3 operators
    addOperatorDelegators(reLST.operatorRegistry, address(reLST.rewardDistributor), 3);

    // The caps for each operator is 1000e18, we will delete the id 2 so we need funds there
    // any number that is more than 1000 should be ok for that experiment
    uint256 AMOUNT = 1002e18;
    // Allocate to cbETH strategy.
    cbETH.approve(address(reLST.coordinator), type(uint256).max);
    uint256 lrtAmount = reLST.coordinator.deposit(CBETH_ADDRESS, AMOUNT);
    // Push funds into EigenLayer.
    vm.prank(EOA, EOA);
    reLST.coordinator.rebalance(CBETH_ADDRESS);
    // Build the empty caps
    IRioLRTOperatorRegistry.StrategyShareCap[] memory zeroStrategyShareCaps = new IRioLRTOperatorRegistry.StrategyShareCap[](1);
    zeroStrategyShareCaps[0] = IRioLRTOperatorRegistry.StrategyShareCap({strategy: CBETH_STRATEGY, cap: 0});

    // Set the caps of CBETH_STRATEGY for operator 2 as "0"
    reLST.operatorRegistry.setOperatorStrategyShareCaps(2, zeroStrategyShareCaps);

    // Try another deposit, we expect revert when we do the rebalance
    reLST.coordinator.deposit(CBETH_ADDRESS, 10e18);
    // Push funds into EigenLayer. Expect revert, due to division by "0"
    skip(reETH.coordinator.rebalanceDelay());
    vm.startPrank(EOA, EOA);
    vm.expectRevert(bytes4(keccak256("DivWadFailed()")));
    reLST.coordinator.rebalance(CBETH_ADDRESS);
    vm.stopPrank();
}
```
Core logic broken, withdrawal/deposits can not be performed.

ratorRegistryV1Admin.sol#L231C5-L270C6  
ratorUtilizationHeap.sol#L94-L110  
g/RioLRTCoordinator.sol#L121-L151  
g/RioLRTDepositPool.sol#L47-L67  
ratorOperations.sol#L51-L68  
g/RioLRTOperatorRegistry.sol#L342-L392  
ratorRegistryV1Admin.sol#L327-L351

## Proof of Concept

no poc

## Recommendation

When removing from the heap also remove the last element from the heap. I am not sure of this, but this might work:
```solidity
function _remove(Data memory self, uint8 i) internal pure {
    self.operators[i] = self.operators[--self.count];
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originatesfrom an incorrect removal operation in the operator utilization heap used by the Rio Network protocol. When the contract owner resets an operator's strategy share cap to zero, the system marks the operator as inactive, sets its utilization to zero and calls the heap's removeByID function. The heap implementation decreases the internal count but fails to clear the slot that previously held the last element; the internal _remove routine copies the element at the old count index into the removed position without resetting the now‑orphaned slot. Consequently, the heap’s stored array still contains a stale operator identifier whose cap is zero. Later, when the protocol builds a fresh heap for allocating deposits, it iterates over the stored operators and computes utilization as allocation.divWad(cap). For the stale entry the cap is zero, causing a division‑by‑zero error that reverts the entire allocation transaction. This revert propagates to the deposit and withdrawal pathways, making further deposits or withdrawals impossible and effectively locking user funds. The bug manifests only after an operator’s cap is set to zero while the heap still reports a non‑zero count, which can be subtle because the heap appears to have the correct number of active operators but contains an invalid entry. The issue was discovered during a formal audit when a forge test that reset an operator’s cap triggered a revert on a subsequent rebalance call, and a manual inspection of the heap’s internal storage revealed that the last element was never cleared. The problem is hard to notice because the heap’s count field is updated, masking the presence of the stale entry until a division operation is performed. To remediate, the removal routine must also clear the vacated slot, for example by decrementing the count before copying the last element or explicitly setting the old last slot to zero, ensuring that no operator with a zero cap remains in the heap and preventing division‑by‑zero failures. This class of bug is a heap‑management flaw that leads to incorrect state persistence and arithmetic errors, violating the protocol’s accounting assumptions that every active operator has a positive cap and that utilization can be safely calculated.
