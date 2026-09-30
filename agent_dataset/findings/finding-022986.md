---
id: 22986
severity: "High"
---

# Selling sUSDe is vulnerable to sandwich at-

## Description

Selling sUSDe is vulnerable to sandwich attacks due to missing slippage protection in the first trade leg.
The protocol has functionality that makes a trade in 2 parts (legs). It only has slippage protection in the second part, but the second part is only executed in certain conditions, leaving the trade without slippage protection. The protocol offers users the functionality to leverage stake and receive leveraged yield. This can be achieved by a borrowed token being wrapped or exchanged into a staking token that is pegged to the borrow token’s value. One of the tokens Notional uses is Ethena's USDe and sUSDe. The user would be receiving leveraged USDe yield. In the case of Ethena/Notional the borrowed token is DAI. Once a user wants to exit BaseStakingVault::_redeemFromNotional is called. There are two options instant redemption or through the withdraw request functionality. If instant redemption is used EthenaLib::_sellStakedUSDe is called.
```solidity
function _executeInstantRedemption(
    address /* account */,
    uint256 vaultShares,
    uint256 /* maturity */,
    RedeemParams memory params
) internal override returns (uint256 borrowedCurrencyAmount) {
    uint256 sUSDeToSell = getStakingTokensForVaultShare(vaultShares);
    // Selling sUSDe requires special handling since most of the liquidity
    // sits inside a sUSDe/sDAI pool on Curve.
    return EthenaLib._sellStakedUSDe(
        sUSDeToSell, BORROW_TOKEN, params.minPurchaseAmount,
        params.exchangeData, params.dexId
    );
}
```
The _sellStakedUSDe function has two trades. The first one swapping from sUSDe to sDAI. The second is only executed if the borrow token is NOT DAI as seen in the code snippet below.
```solidity
function _sellStakedUSDe(
    uint256 sUSDeAmount,
    address borrowToken,
    uint256 minPurchaseAmount,
    bytes memory exchangeData,
    uint16 dexId
) internal returns (uint256 borrowedCurrencyAmount) {
    Trade memory sDAITrade = Trade({
        tradeType: TradeType.EXACT_IN_SINGLE,
        sellToken: address(sUSDe),
        buyToken: address(sDAI),
        amount: sUSDeAmount,
        // of the trade.
        deadline: block.timestamp,
        exchangeData: abi.encode(CurveV2Adapter.CurveV2SingleData({
            pool: 0x167478921b907422F8E88B43C4Af2B8BEa278d3A,
            fromIndex: 1, // sUSDe
            toIndex: 0 // sDAI
        }))
    });
    (/* */, uint256 sDAIAmount) = sDAITrade._executeTrade(uint16(DexId.CURVE_V2));
    // Unwraps the sDAI to DAI
    uint256 daiAmount = sDAI.redeem(sDAIAmount, address(this), address(this));
    if (borrowToken != address(DAI)) {
        Trade memory trade = Trade({
            tradeType: TradeType.EXACT_IN_SINGLE,
            sellToken: address(DAI),
            buyToken: borrowToken,
            amount: daiAmount,
            limit: minPurchaseAmount,
            deadline: block.timestamp,
            exchangeData: exchangeData
        });
        // Trades the unwrapped DAI back to the given token.
        (/* */, borrowedCurrencyAmount) = trade._executeTrade(dexId);
    } else {
        borrowedCurrencyAmount = daiAmount;
    }
}
```
There is NO slippage protection on the first trade. The reason being that slippage is checked in the second trade. However the second trade is only executed in the borrow token is NOT DAI. This opens the possibility of the trade being sandwich attacked by MEV bots stealing large portions of user funds, if the borrowed token is DAI, because the second trade would NOT be executed. Hence no slippage at all would be enforced in the transaction. Loss of funds due to sandwich attack.

## Proof of Concept

no poc

## Recommendation

Add a slippage parameter to the first trade as well or use the minPurchaseAmount parameter as a minAmountOut:
```solidity
function _sellStakedUSDe(
    uint256 sUSDeAmount,
    address borrowToken,
    uint256 minPurchaseAmount,
    bytes memory exchangeData,
    uint16 dexId
) {
    ...
    uint256 daiAmount = sDAI.redeem(sDAIAmount, address(this), address(this));
    if (borrowToken != address(DAI)) {
        Trade memory trade = Trade({
            tradeType: TradeType.EXACT_IN_SINGLE,
            sellToken: address(DAI),
            buyToken: borrowToken,
            amount: daiAmount,
            limit: minPurchaseAmount,
            deadline: block.timestamp,
            exchangeData: exchangeData
        });
        // Trades the unwrapped DAI back to the given token.
        (/* */, borrowedCurrencyAmount) = trade._executeTrade(dexId);
    } else {
        borrowedCurrencyAmount = daiAmount;
        require(borrowedCurrencyAmount >= minPurchaseAmount);
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

Selling a staked version of USDe (sUSDe) through the instant redemption path of the Notional leveraged vault is vulnerable to sandwich attacks because the first trade that swaps sUSDe for sDAI on Curve does not enforce any slippage limit. The contract only checks a minimum purchase amount in the second trade, which converts the unwrapped DAI into the borrow token, but this second trade is skipped when the borrow token is DAI itself. Consequently, when a user redeems and the borrowed token is DAI, the transaction executes a single trade without any protection against price movement between the time the transaction is submitted and the time it is mined. A malicious MEV bot can observe the pending transaction, front‑run it with a large trade that moves the sUSDe/sDAI pool price, and then back‑run the user’s transaction, causing the user to receive far fewer DAI than expected or even zero. From the user’s perspective the UI shows a successful redemption but the received amount is dramatically lower than the expected minimum, effectively making funds disappear. The issue occurs only in the instant redemption flow, only when the borrow token is DAI, and only because the contract assumes the second trade will always provide slippage safety. It was discovered during a manual audit of the leveraged vault code where the trade logic was examined and the conditional execution of the second leg was noted. The bug is subtle because the presence of a slippage check in the second leg gives a false sense of security, masking the fact that the first leg can be exploited when the second leg is bypassed. To remediate, the contract should enforce a slippage constraint on the sUSDe→sDAI swap, for example by adding a minimum amount‑out check comparable to the minPurchaseAmount parameter, or by explicitly requiring the DAI amount received to meet the user‑specified minimum. This would align the protection model with the business logic that users expect to receive at least a certain amount of borrowed token when they redeem, preventing the sandwich attack vector and preserving accounting integrity.
