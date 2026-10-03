---
id: 25551
severity: "Medium"
---

# Trader Can Set Wrong TP and SL

## Description

In OstiumTrading::updateSl(), a validation is present for the maximum stop loss (SL) distance. However, [there](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/test/foundry/OstiumTradingCallback.t.sol#L1642>) is no validation for the opposite scenario, as seen in OstiumTrading::openTrade() at [L202](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumTrading.sol#L202>).

This absence of validation permits the setting of a stop loss for an amount greater than the open price when initiating a long position and for setting a smaller amount when initiating a short position.

Consequently, this issue introduces the potential for errors, whereby automation could mistakenly trigger the closure of a position upon reaching this price, behaving akin to a take-profit order, contrary to its intended function.

The same issue arises in OstiumTrading::updateTp(), which lacks validation to ensure that the new take profit (TP) is greater than the open price for long positions and smaller for short positions.

## Proof of Concept

```solidity
function test_wrong_updateSl() public {
    uint192 newSL = 31000e18; // bigger than open price which is 30000e18
    mockTradingStorage.storeTrade( t, IOstiumTradingStorage.TradeInfo( 1, t.collateral * 1e12 * t.leverage / 100 * PRECISION_18 / t.openPrice, t.leverage, 0, 0, 0, false ) );
    vm.prank(DEFAULT_SENDER);
    trading.updateSl(0, 0, newSL);
}
function test_wrong_updateTp() public {
    uint256 tradeId = 1;
```

mockTradingStorage.storeTrade( t, IOstiumTradingStorage.TradeInfo( tradeId, t.collateral * 1e12 * t.leverage / 100 * PRECISION_18 / t.openPrice, t.leverage, 0, 0, 0, false )

```solidity
);
vm.prank(DEFAULT_SENDER);
vm.expectEmit(true, true, true, true, address(trading));
emit TpUpdated(tradeId, DEFAULT_SENDER, 0, 0, 28000e18); // lower than
open price = 30000e18
trading.updateTp(0, 0, 28000e18);
}
```

## Recommendation

Change the validation on [L381](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumTrading.sol#L381>) in OstiumTrading::updateSl() to:

```solidity
if (newSl != 0 && (t.buy ? newSl < t.openPrice - maxSlDist || newSl >= t.openPrice : newSl > t.openPrice + maxSlDist || newSl <= t.openPrice))
revert WrongSL();
```

Add this validation to OstiumTrading::updateTp():

```solidity
if (newTp != 0 && (t.buy ? newTp <= t.openPrice : newTp >= t.openPrice)) {
    revert WrongTP();

}
```
