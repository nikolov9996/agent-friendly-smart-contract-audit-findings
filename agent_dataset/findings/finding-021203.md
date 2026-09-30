---
id: 21203
severity: "High"
---

# In Dolomite, when opening a borrow position, the holding position in the Registry will never be updated due to the `removePosition` flag being set to true

## Description

```solidity
Whenever some of the connectors opens or closes a position, it is updated in the registry.

Usually if/when a position is closed (all asset amount withdrawn / borrow position closed in its entirety, etc.), the holding position is updated with the flag `true` for `bool removePosition`.

In Dolomite, whenever we open a new borrow position, the flag is also set to `true` which means that the position should be removed, and again when closing the borrow position, the flag is also set to `true`.

This will lead to that position never being accounted for in the Registry.
```

## Proof of Concept

```solidity
In Dolomite, whenever we want to open a borrow position, we can call the `openBorrowPosition()` function:
    
    function openBorrowPosition(uint256 marketId, uint256 _amountWei, uint256 accountId)
        public
        onlyManager
        nonReentrant
    {
        address token = dolomiteMargin.getMarketTokenAddress(marketId);

        if (!registry.isTokenTrusted(vaultId, token, address(this))) {
            revert IConnector_UntrustedToken(token);
        }
        // borrow
        borrowPositionProxy.openBorrowPosition(
            0, accountId, marketId, _amountWei, AccountBalanceHelper.BalanceCheckFlag.None
        );
        registry.updateHoldingPosition(
            vaultId, registry.calculatePositionId(address(this), DOL_POSITION_ID, ""), abi.encode(accountId), "", true
        );
    }

As we can see, when calling the `registry.updateHoldingPosition` the `removePosition` flag is set to `true` (the last argument in the function call).

Usually this is done when we want to either close a position or we’ve emptied the market/pool (our balance/share is 0) and we’re closing it, here is an example from the same connector Dolomite properly utilizing this in the `withdraw` function:
    
    function withdraw(uint256 marketId, uint256 _amount) public onlyManager nonReentrant {
        address token = dolomiteMargin.getMarketTokenAddress(marketId);
        depositWithdrawalProxy.withdrawWeiFromDefaultAccount(
            marketId, _amount, AccountBalanceHelper.BalanceCheckFlag.None
        );
        // Update token
        _updateTokenInRegistry(token);
        (uint256[] memory markets,,,) = dolomiteMargin.getAccountBalances(Info(address(this), 0));
        if (markets.length == 0) {
            registry.updateHoldingPosition(
                vaultId, registry.calculatePositionId(address(this), DOL_POSITION_ID, ""), abi.encode(0), "", true
            );
        }
    }

We can also see that when closing a borrow position in the same connector, the flag is also set to true:
    
    function closeBorrowPosition(uint256[] memory marketIds, uint256 accountId) public onlyManager nonReentrant {
        // repay
        borrowPositionProxy.closeBorrowPosition(accountId, 0, marketIds);
        registry.updateHoldingPosition(
            vaultId, registry.calculatePositionId(address(this), DOL_POSITION_ID, ""), abi.encode(accountId), "", true
        );
    }

Due to the following circuit-breaker check, the borrow position would never be updated as part of the `holdingPositions` array:
    
    if (positionIndex == 0 && removePosition) return type(uint256).max;

The `positionIndex` is based on the `isPositionUsed` mapping:
    
    bytes32 holdingPositionId = keccak256(abi.encode(msg.sender, _positionId, _data));
    uint256 positionIndex = vault.isPositionUsed[holdingPositionId];

Since that mapping value of the holdingPositionId would have never been initiated, due to the circuit-breaker check above returning type(uint256).max, it would be 0, thus interrupting the function flow.

If the flag hasn’t been set to true, the function flow would continue to the end, calling the other `updateHoldingPosition` function, and updating the `isPositionUsed` mapping:
    
    return updateHoldingPosition(vault, vaultId, _positionId, _data, additionalData, positionIndex, holdingPositionId);

This position would have never been accounted for in the Registry, and if the strategy’s actions are based on Registry data, it can fail to close the position in-time, possibly leading to liquidations and bad debt.
```

## Recommendation

```solidity
Set the `removePosition` flag on the `openBorrowPosition` when calling the `updateHoldingPosition` function to `false`.
```

> Both open and close borrow are impacted.

## Derived Narrative

The following field is derived content and may not be source-grounded:

In the Dolomite connector a borrow position is created by calling openBorrowPosition, which subsequently invokes registry.updateHoldingPosition with the boolean flag removePosition set to true. The removePosition flag is intended to signal that a position should be removed from the registry, typically when the position is fully closed or the token balance becomes zero. By setting this flag to true during the opening of a borrow position, the registry’s internal circuit‑breaker logic interprets the call as a removal request. The circuit‑breaker checks if the position index is zero and the flag is true, and if so it returns type(uint256).max, preventing any further updates to the isPositionUsed mapping that records that the holding position exists. Consequently the newly opened borrow position is never recorded in the Registry’s holdingPositions array. This omission means that any downstream logic that relies on the Registry – for example, strategies that monitor positions to trigger timely repayments or liquidations – will not see the open borrow position. When the protocol later attempts to close the position, the Registry still believes the position does not exist, which can cause the close operation to fail, potentially leading to forced liquidations, bad debt, or loss of collateral. The vulnerability manifests whenever any user or manager opens a borrow position through the connector, regardless of market or amount, and it affects all participants whose positions are managed by the affected vault. It was discovered during a Code4rena audit by inspecting the flag usage in the openBorrowPosition function and tracing the registry’s updateHoldingPosition implementation. The bug is subtle because the UI may show that a borrow position was opened, yet the internal accounting appears unchanged, giving no immediate error signal. The proper fix is to pass false for the removePosition flag when updating the holding position during an openBorrowPosition call, ensuring the position is added to the Registry, while retaining true for genuine removal scenarios such as closing or emptying a position. This change restores correct accounting, prevents hidden positions, and aligns the Registry’s state with the protocol’s business logic for borrowing and repayment.
