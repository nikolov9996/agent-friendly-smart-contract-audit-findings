---
id: 25536
severity: "Low/Info"
---

# Use of Magic Numbers

## Description

Several instances of magic numbers are present throughout the contracts:

- The validation for slippageP in OstiumTrading::openTrade() on [L169](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/869392c4c9114ad468f6c2ea7e425269faf2fe2b/src/OstiumTrading.sol#L169>).
- [L117](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumOpenPnl.sol#L117>) in OstiumOpenPnl::getOpenPnl().
- [L401](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTrading.sol#L401>) in OstiumTrading::topUpCollateral().
- [L149](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingCallbacks.sol#L149>) in OstiumTradingCallbacks::openTradeMarketCallback().
- [L446](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/1b70cffbac621d39e321c159e45c048b703add92/src/OstiumTradingCallbacks.sol#L446>) in OstiumTradingCallbacks::registerTrade().

## Proof of Concept

No PoC provided.

## Recommendation

It is recommended to review the contracts and replace these magic numbers with constants for improved clarity. Not all instances of them are mentioned in the description.
