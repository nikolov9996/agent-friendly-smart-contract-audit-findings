---
id: 21752
severity: "High"
---

# Failure to update dirty flag in `transferToUnoccupiedPlot` prevents reward accumulation on valid plot

## Description

The [`transferToUnoccupiedPlot`](https://github.com/code-423n4/2024-07-munchables/blob/94cf468aaabf526b7a8319f7eba34014ccebe7b9/src/managers/LandManager.sol#L199) function allows a user to transfer their Munchable to another unoccupied plot from the same landlord. This can be used for example by users currently staked in an invalid plot marked as “dirty”, meaning they will not be earning any rewards, to transfer to a valid plot so they can start earning rewards again.

Since the function checks that the transfer is to a valid plot, it should mean users are now eligible to start earning rewards again. However, it doesn’t update the user’s dirty flag back to false, meaning the user will still not be earning any rewards even after they have moved to a valid plot.

```solidity
function transferToUnoccupiedPlot(uint256 tokenId, uint256 plotId)
    external
    override
    forceFarmPlots(msg.sender)
    notPaused
{
    (address mainAccount,) = _getMainAccountRequireRegistered(msg.sender);
    ToilerState memory _toiler = toilerState[tokenId];
    uint256 oldPlotId = _toiler.plotId;
    uint256 totalPlotsAvail = _getNumPlots(_toiler.landlord);
    if (_toiler.landlord == address(0)) revert NotStakedError();
    if (munchableOwner[tokenId] != mainAccount) revert InvalidOwnerError();
    if (plotOccupied[_toiler.landlord][plotId].occupied) {
        revert OccupiedPlotError(_toiler.landlord, plotId);
    }
    if (plotId >= totalPlotsAvail) revert PlotTooHighError();

    toilerState[tokenId].latestTaxRate = plotMetadata[_toiler.landlord].currentTaxRate;
    plotOccupied[_toiler.landlord][oldPlotId] = Plot({occupied: false, tokenId: 0});
    plotOccupied[_toiler.landlord][plotId] = Plot({occupied: true, tokenId: tokenId});

    emit FarmPlotLeave(_toiler.landlord, tokenId, oldPlotId);
    emit FarmPlotTaken(toilerState[tokenId], tokenId);
}
```

The next time [`_farmPlots`](https://github.com/code-423n4/2024-07-munchables/blob/94cf468aaabf526b7a8319f7eba34014ccebe7b9/src/managers/LandManager.sol#L232) is called, since dirty is still true, it’ll be skipped, accumulating no rewards.

```solidity
function _farmPlots(address _sender) internal {
    ...
    for (uint8 i = 0; i < staked.length; i++) {
        ...
        if (_toiler.dirty) continue;
        ...
        );
    }
    accountManager.updatePlayer(mainAccount, renterMetadata);
}
```

## Proof of Concept

no poc

## Recommendation

Update the `transferToUnoccupiedPlot` function to reset the dirty flag to false and update the `lastToilDate` if it was previously marked as dirty when a user successfully transfers to a valid plot. This will ensure that users start earning rewards again once they are on a valid plot.

```solidity
function transferToUnoccupiedPlot(uint256 tokenId, uint256 plotId)
    external
    override
    forceFarmPlots(msg.sender)
    notPaused
{
    (address mainAccount,) = _getMainAccountRequireRegistered(msg.sender);
    ToilerState memory _toiler = toilerState[tokenId];
    uint256 oldPlotId = _toiler.plotId;
    uint256 totalPlotsAvail = _getNumPlots(_toiler.landlord);
    if (_toiler.landlord == address(0)) revert NotStakedError();
    if (munchableOwner[tokenId] != mainAccount) revert InvalidOwnerError();
    if (plotOccupied[_toiler.landlord][plotId].occupied) {
        revert OccupiedPlotError(_toiler.landlord, plotId);
    }
    if (plotId >= totalPlotsAvail) revert PlotTooHighError();
    // ADD HERE
    if (_toiler.dirty) {
        toilerState[tokenId].lastToilDate = block.timestamp;
        toilerState[tokenId].dirty = false;
    }
    //
    toilerState[tokenId].latestTaxRate = plotMetadata[_toiler.landlord].currentTaxRate;
    plotOccupied[_toiler.landlord][oldPlotId] = Plot({occupied: false, tokenId: 0});
    plotOccupied[_toiler.landlord][plotId] = Plot({occupied: true, tokenId: tokenId});

    emit FarmPlotLeave(_toiler.landlord, tokenId, oldPlotId);
    emit FarmPlotTaken(toilerState[tokenId], tokenId);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a state‑inconsistency bug in the LandManager contract where the transferToUnoccupiedPlot function allows a user to move a Munchable token from a dirty (invalid) plot to a valid, unoccupied plot but fails to reset the ToilerState.dirty flag and the associated lastToilDate. The dirty flag is used by the internal _farmPlots routine to decide whether a token should participate in reward calculation; when the flag remains true, the routine skips the token, resulting in no reward accrual even though the token now resides on a plot that should generate earnings. The root cause is the omission of a state update after the successful transfer – the function checks plot validity and updates occupancy, yet it never clears the dirty flag. Exploitation is straightforward: any user whose token is marked dirty can invoke transferToUnoccupiedPlot, see the transaction succeed, and still observe that their reward balance does not increase. From the user’s perspective the UI shows the token on a valid plot, they expect to start earning again, but the balance remains unchanged, creating the impression that funds have disappeared. The impact is a loss of expected reward income for token owners and a reduction in protocol‑generated revenue, although no assets are directly stolen. The bug manifests only when a token’s dirty flag is true at the moment of transfer; otherwise normal reward flow proceeds. It affects all stakers who may become dirty due to previous plot invalidation and then attempt to recover by moving. The issue was discovered during a manual audit by Code4rena, where the auditor noticed that the dirty flag is never cleared after a transfer. It can be hard to notice because the contract does not revert or emit an error; the only symptom is a flat reward balance despite a successful plot change. The proper remediation is to reset the dirty flag to false and update lastToilDate to the current block timestamp within transferToUnoccupiedPlot when the token is moved from a dirty plot, thereby re‑enabling reward calculation and aligning the contract state with the business rule that a token on a non‑dirty plot must earn rewards.
