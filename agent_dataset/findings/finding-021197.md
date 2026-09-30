---
id: 21197
severity: "High"
---

# `Registry.sol#updateHoldingPosition` remove position logic is incorrect: should use `ownerConnector` instead of `calculatorConnector` when calculating `holdingPositionId`

## Description

When removing a `holdingPosition` that is not at the back of `holdingPositions` array, the `holdingPositionId` is incorrectly calculated. This will mess up the position index, and ultimately mess up TVL calculation.

When removing a position in `updateHoldingPosition`, if the index of the position is not the last, it will do a swap between the current index and the last index, and remove the last position in `holdingPositions` array. However, the issue is when updating `vault.isPositionUsed[holdingPositionId]` index, the `holdingPositionId` is not correct.

It should be using `vault.holdingPositions[positionIndex].ownerConnector` instead of `vault.holdingPositions[positionIndex].calculatorConnector`.

This would be an issue for most of the token-holding positions because the `calculateorConnector` is the `AccountingManager` while the `ownerConnector` is the connector’s own address.

```solidity
function updateHoldingPosition(
    uint256 vaultId,
    bytes32 _positionId,
    bytes calldata _data,
    bytes calldata additionalData,
    bool removePosition
) public vaultExists(vaultId) returns (uint256) {
    Vault storage vault = vaults[vaultId];
    if (!vault.connectors[msg.sender].enabled) revert UnauthorizedAccess();
    if (!vault.trustedPositionsBP[_positionId].isEnabled) revert InvalidPosition(_positionId);
    bytes32 holdingPositionId = keccak256(abi.encode(msg.sender, _positionId, _data));
    uint256 positionIndex = vault.isPositionUsed[holdingPositionId];
    if (positionIndex == 0 && removePosition) return type(uint256).max;
    if (removePosition) {
        if (positionIndex < vault.holdingPositions.length - 1) {
            vault.holdingPositions[positionIndex] = vault.holdingPositions[vault.holdingPositions.length - 1];
            vault.isPositionUsed[keccak256(
                abi.encode(
                    vault.holdingPositions[positionIndex].ownerConnector,
                    vault.holdingPositions[positionIndex].positionId,
                    vault.holdingPositions[positionIndex].data
                )
            )] = positionIndex;
        }
        vault.holdingPositions.pop();
        vault.isPositionUsed[holdingPositionId] = 0;
        emit HoldingPositionUpdated(vaultId, _positionId, _data, additionalData, removePosition, positionIndex);
        return type(uint256).max;
    }
    return
        updateHoldingPosition(vault, vaultId, _positionId, _data, additionalData, positionIndex, holdingPositionId);
}
```

## Proof of Concept

We will give an example of how this bug will mess up the position index and ultimately lead to incorrect TVL.

Add the following test code in `BaseConnector.t.sol`. It does the following:

1. Create 3 connectors, with the order [1, 2, 3] (with a dummy connector up front), and deal 10e6 USDC to each of them.
2. Check that current TVL is 30e6.
3. Move all USDC from connector 1 to 3. This should remove connector 1’s position. The current position array is [3, 2].
4. Move all USDC from connector 3 to 2. This should remove connector 3’s position. However, since the `positionIndex` is not correctly updated in step 3, the connector 3’s `positionIndex` is still 3. This in `updateHoldingPosition()` will result in popping the position at the back (which is actually position 2).
5. Check that current TVL is 0: because connector 2 is holding all the USDC but it has been popped out in step 4.

```solidity
function testRemoveConnectorBug() public {
    vm.startPrank(owner);
    BaseConnector connector3;
    connector3 = new BaseConnector(BaseConnectorCP(registry, 0, swapHandler, noyaOracle));
    addConnectorToRegistry(vaultId, address(connector3));

    // Step 1: Deal 10e6 USDC tokens to all 3 connectors.
    uint256 amount = 10 * 1e6;
    _dealWhale(baseToken, address(connector), USDC_Whale, amount);
    _dealWhale(baseToken, address(connector2), USDC_Whale, amount);
    _dealWhale(baseToken, address(connector3), USDC_Whale, amount);
    vm.startPrank(owner);
    connector.updateTokenInRegistry(USDC);
    connector2.updateTokenInRegistry(USDC);
    connector3.updateTokenInRegistry(USDC);

    // Make sure the TVL is 30e6.
    uint tvl = accountingManager.TVL();
    assertEq(tvl, 30e6);

    // Step 2: Move all USDC from connector 1 to connector 3. TVL is still 30e6.
    address[] memory tokens = new address[](1);
    tokens[0] = USDC;
    uint256[] memory amounts = new uint256[](1);
    amounts[0] = amount;
    {
        connector.transferPositionToAnotherConnector(tokens, amounts, "", address(connector3));
        uint tvl = accountingManager.TVL();
        assertEq(tvl, 30e6);
    }

    // Step 3: Move all USDC from connector 3 to connector 2. TVL is now ZERO.
    {
        amounts[0] = 2 * amount;
        connector3.transferPositionToAnotherConnector(tokens, amounts, "", address(connector2));
        uint tvl = accountingManager.TVL();
        assertEq(tvl, 0);
    }
}
```

## Recommendation

Use `vault.holdingPositions[positionIndex].ownerConnector` to calculate holdingPositionId.

Fix in commit aef35f768753277552c65ffecf199ea73d0cd058.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the logic that removes a holding position from the vault's holdingPositions array. When a position that is not the last element is removed, the contract swaps the element at the target index with the last element and then pops the array. The code then updates the mapping that tracks which position identifier is stored at which index. However, the identifier (holdingPositionId) is recomputed using the field calculatorConnector, which points to the AccountingManager contract, instead of using ownerConnector, which holds the address of the connector that actually owns the position. Because the two fields differ for most token‑holding positions, the mapping is updated with an incorrect key. As a result the internal index for the swapped position becomes stale, causing subsequent removals to delete the wrong array entry. This mis‑alignment propagates to the total value locked (TVL) calculation performed by the AccountingManager: the protocol believes a position has been removed while the underlying tokens are still held by a different connector, leading to a TVL that drops to zero or otherwise becomes inaccurate. The bug is triggered only when a non‑terminal position is removed, which is a common scenario during token migrations or connector rebalancing. Users experience symptoms such as a sudden disappearance of their reported balances, a dashboard showing zero TVL despite deposited assets, or refunds that never arrive. The issue was discovered during a Code4rena audit by constructing a test that moved assets across three connectors; after two sequential removals the TVL incorrectly reported zero. The problem is subtle because the contract does not revert or emit an explicit error; the state appears consistent but accounting data is corrupted, making it hard to detect without explicit TVL checks. The correct fix is to recompute holdingPositionId with the ownerConnector field when updating the isPositionUsed mapping, ensuring the mapping key matches the actual owner of the position. This change restores the integrity of the position index and guarantees that TVL reflects the true amount of assets held by the protocol.
