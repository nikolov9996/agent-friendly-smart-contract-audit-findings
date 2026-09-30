---
id: 17347
severity: "High"
---

# Not enough margin pulled or burned from user when adding to a position

## Description

When adding to a position, the amount of margin pulled from the user is not as much as it should be, which leaks value from the protocol, lowering the collateralization ratio of `tigAsset`.

## Proof of Concept

In `Trading.addToPosition` the `_handleDeposit` function is called like this:

```solidity
_handleDeposit(
    _trade.tigAsset,
    _marginAsset,
    _addMargin - _fee,
    _stableVault,
    _permitData,
    _trader
);
```

The third parameter with the value of `_addMargin - _fee` is the amount pulled (or burned in the case of using `tigAsset`) from the user. The `_fee` value is calculated as part of the position size like this:

```solidity
uint _fee = _handleOpenFees(_trade.asset, _addMargin*_trade.leverage/1e18, _trader, _trade.tigAsset, false);
```

The `_handleOpenFees` function mints `_tigAsset` to the referrer, to the `msg.sender` (if called by a function meant to be executed by bots) and to the protocol itself. Those minted tokens are supposed to be part of the `_addMargin` value paid by the user. Hence using `_addMargin - _fee` as the third parameter to `_handleDeposit` is going to pull or burn less margin than what was accounted for.

An example for correct usage can be seen in `initiateMarketOrder`:

```solidity
uint256 _marginAfterFees = _tradeInfo.margin - _handleOpenFees(_tradeInfo.asset, _tradeInfo.margin*_tradeInfo.leverage/1e18, _trader, _tigAsset, false);
uint256 _positionSize = _marginAfterFees * _tradeInfo.leverage / 1e18;
_handleDeposit(_tigAsset, _tradeInfo.marginAsset, _tradeInfo.margin, _tradeInfo.stableVault, _permitData, _trader);
```

Here the third parameter to `_handleDeposit` is not `_marginAfterFees` but `_tradeInfo.margin` which is what the user has input on and is supposed to pay.

## Recommendation

In `Trading.addToPosition` call the `_handleDeposit` function without subtracting the `_fee` value:

```solidity
_handleDeposit(
    _trade.tigAsset,
    _marginAsset,
    _addMargin,
    _stableVault,
    _permitData,
    _trader
);
```

The Warden has shown how, due to an incorrect computation, less margin is used when adding to a position.

While the loss of fees can be considered Medium Severity, I believe that the lack of checks is ultimately allowing for more leverage than intended which not only breaks invariants but can cause further issues (sponsor cited Fees as a defense mechanism against abuse).

For this reason, I believe the finding to be of High Severity.

**[GainsGoblin (Tigris Trade) resolved](https://github.com/code-423n4/2022-12-tigris-findings/issues/659#issuecomment-1407828021):**

Mitigation: <https://github.com/code-423n4/2022-12-tigris/pull/2#issuecomment-1419177303>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an under‑collateralisation bug that occurs when a trader adds margin to an existing position through the Trading.addToPosition function. The contract calculates a fee that is minted to referrers and the protocol, but then mistakenly subtracts that fee from the amount passed to the internal _handleDeposit call. As a result the protocol records that the full _addMargin amount has been locked, while in reality only _addMargin minus the fee is taken from the user’s wallet (or burned when using tigAsset). This mismatch lowers the actual collateralisation ratio of the tigAsset position, breaking the invariant that a position must be fully backed by the declared margin. The bug can be exploited by opening a leveraged position with less real collateral than the contract believes, allowing an attacker to obtain higher leverage, increase the chance of liquidation, or cause the protocol to lose value because fees are effectively double‑counted. The issue manifests whenever addToPosition is called, i.e., any time a user tries to increase margin on a position, and it affects all participants who rely on correct margin accounting – traders, lenders, and the protocol itself. It was discovered during a manual audit by Code4rena when the fee handling logic was compared with the correct pattern used in initiateMarketOrder, revealing that the fee was being deducted from the deposited amount instead of being accounted for separately. The problem is subtle because the UI continues to display the expected margin amount and the position size appears correct, so users may not notice that less collateral is actually locked until an unexpected liquidation or a missing refund occurs. From a user perspective the symptoms are a position that seems properly funded but later gets liquidated prematurely, or a situation where a refund or remaining balance is lower than expected. The bug belongs to the class of margin‑accounting errors or fee double‑counting bugs that violate the business logic that each unit of margin must be fully backed. The recommended fix is to invoke _handleDeposit with the full _addMargin value, removing the subtraction of _fee, and to handle fee minting as a separate step that does not reduce the amount of collateral taken from the user. This restores the correct collateralisation ratio and prevents the protocol from being exposed to unintended leverage.
