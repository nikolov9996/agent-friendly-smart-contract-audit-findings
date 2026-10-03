---
id: 25537
severity: "Medium"
---

# Oracle fees should be payed upfront to protect the protocol from failed performeUpkeep() calls

## Description

At the moment oracle fees are payed after the trades have been finalized, either in [registerTrade()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L420>), [openTradeMarketCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L182>) or [closeTradeMarketCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L231>).

[There](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/interfaces/IOstiumPairsStorage.sol#L21>) are some edge cases in which the trade does not get finalized, but the automation/upkeep is still performed, so the protocol incurs these losses.

For example, if there is not a trade in [openTradeMarketCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L140-L142>), fees will not be charged (this may happen if the user cancels the pending market open order after the [timeout](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTrading.sol#L493>), but chainlink triggers the upkeep after closing).

## Proof of Concept

No PoC provided.

## Recommendation

Make the user pay oracle fees when they open the trades.
