---
id: 25552
severity: "Low/Info"
---

# In OstiumTradesUpKeep, _getLimitOrdersToTrigger() and _getOpenOrdersToTrigger() return tradesToTrigger with 1 extra length

## Description

In [OstiumTradesUpKeep::_getLimitOrdersToTrigger()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradesUpKeep.sol#L244-L248>) and [OstiumTradesUpKeep::_getOpenOrdersToTrigger()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradesUpKeep.sol#L363-L367>), tradesToTrigger are returned with 1 extra length due to incorrect ++tradesToTrigger operation. tradesToTriggerIndex starts at 0 and increases whenever a trade is found, so it is always ahead of the biggest index by 1 already, representing the length.

## Proof of Concept

No PoC provided.

## Recommendation

Remove ++ from the conditions if (++tradesToTriggerIndex < tradesToTrigger.length). Additionally, check if the length of the array [here](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradesUpKeep.sol#L137>) is 0 instead of the first trader.
