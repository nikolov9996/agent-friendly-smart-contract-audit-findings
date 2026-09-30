---
id: 18286
severity: "High"
---

# `KangarooVault.removeCollateral` updates storage without actually removing collateral, resulting in lost collateral

## Description

The admin can call `KangarooVault.addCollateral` to add additional collateral to a Power Perp position.
    
```solidity
function addCollateral(uint256 additionalCollateral) external requiresAuth nonReentrant {
    SUSD.safeApprove(address(EXCHANGE), additionalCollateral);
    EXCHANGE.addCollateral(positionData.positionId, additionalCollateral);

    usedFunds += additionalCollateral;
    positionData.totalCollateral += additionalCollateral;

    emit AddCollateral(positionData.positionId, additionalCollateral);
}
```

This transfers `SUSD` to the `EXCHANGE` and updates the `usedFunds` and `positionData.totalCollateral`.

The function `KangarooVault.removeCollateral` allows the admin to remove collateral if a position is healthy enough.
    
```solidity
function removeCollateral(uint256 collateralToRemove) external requiresAuth nonReentrant {
    (uint256 markPrice,) = LIQUIDITY_POOL.getMarkPrice();
    uint256 minColl = positionData.shortAmount.mulWadDown(markPrice);
    minColl = minColl.mulWadDown(collRatio);

    require(positionData.totalCollateral >= minColl + collateralToRemove);
        
    usedFunds -= collateralToRemove;
    positionData.totalCollateral -= collateralToRemove;

    emit RemoveCollateral(positionData.positionId, collateralToRemove);
}    
```

The issue is that this function does not call `EXCHANGE.removeCollateral`.  
While it updates storage, it does not actually retrieve any collateral.

## Proof of Concept

Amend this test to `KangarooVault.t.sol`, which shows how collateral is not transferred upon calling `removeCollateral()`.
    
```solidity
function testCollateralManagement() public {
    uint256 amt = 1e18;
    uint256 collDelta = 1000e18;

    kangaroo.openPosition(amt, 0);
    skip(100);
    kangaroo.executePerpOrders(emptyData);
    kangaroo.clearPendingOpenOrders(0);

    (,,,,,,, uint256 initialColl,) = kangaroo.positionData();
    uint256 balanceBefore = susd.balanceOf(address(kangaroo));

    kangaroo.addCollateral(collDelta);
    uint256 balanceAfter = susd.balanceOf(address(kangaroo));
    assertEq(collDelta, balanceBefore - balanceAfter);
    (,,,,,,, uint256 finalColl,) = kangaroo.positionData();

    assertEq(finalColl, initialColl + collDelta);

    uint256 balanceBefore2 = susd.balanceOf(address(kangaroo));
    kangaroo.removeCollateral(collDelta);
    uint256 balanceAfter2 = susd.balanceOf(address(kangaroo));
    assertEq(0, balanceAfter2 - balanceBefore2); // @audit collateral not removed

    (,,,,,,, uint256 newColl,) = kangaroo.positionData();

    assertEq(newColl, initialColl);
}
```

## Recommendation

Ensure `Exchange.removeCollateral` is called:
    
```solidity
function removeCollateral(uint256 collateralToRemove) external requiresAuth nonReentrant {
    (uint256 markPrice,) = LIQUIDITY_POOL.getMarkPrice();
    uint256 minColl = positionData.shortAmount.mulWadDown(markPrice);
    minColl = minColl.mulWadDown(collRatio);

    require(positionData.totalCollateral >= minColl + collateralToRemove);
        
    usedFunds -= collateralToRemove;
    positionData.totalCollateral -= collateralToRemove;

    EXCHANGE.removeCollateral(positionData.positionId, collateralToRemove);
    emit RemoveCollateral(positionData.positionId, collateralToRemove);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the collateral withdrawal function of the vault contract. The function is intended to let the admin remove a portion of the SUSD collateral that backs a perpetual position when the position satisfies a health check. It correctly computes the minimum required collateral, checks that the total collateral stored in the contract is sufficient, and then updates the internal accounting variables usedFunds and positionData.totalCollateral by subtracting the requested amount. However, the function never calls the external exchange contract that actually holds the SUSD tokens. As a result, the storage reflects a lower collateral amount while the SUSD tokens remain locked in the exchange and are never transferred back to the vault. The root cause is a missing external call – the code updates only internal state and omits the required EXCHANGE.removeCollateral invocation. An attacker or any privileged caller can invoke removeCollateral expecting to retrieve funds, but the call will silently succeed without moving any tokens, leaving the caller’s balance unchanged. From a user’s perspective the UI may show that the collateral amount has decreased, yet the wallet balance stays the same, creating a discrepancy that can be confusing and may be interpreted as a loss of funds. The impact is high because collateral that appears to be withdrawn is actually still held by the exchange, breaking accounting invariants, potentially leading to under‑collateralized positions, liquidation risk, and loss of trust in the protocol. The bug manifests whenever the admin calls removeCollateral on a healthy position after having added collateral earlier. It was discovered during an audit test that measured the SUSD balance before and after the call and observed a zero delta despite the internal collateral counter decreasing. The issue is hard to notice because the contract’s internal state appears consistent and the missing token transfer does not emit an event, so external observers may not see any error. This class of bug falls under incomplete external state synchronization or accounting mismatch, where internal bookkeeping diverges from actual token balances. To remediate, the contract must invoke EXCHANGE.removeCollateral after adjusting its storage, or alternatively retrieve the tokens first and then update the accounting, ensuring that the external token balance and internal records stay in sync.
