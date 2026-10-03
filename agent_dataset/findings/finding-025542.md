---
id: 25542
severity: "Medium"
---

# OstiumPriceUpKeep::performUpKeep() does not correctly handle possible reverts

## Description

OstiumPriceUpKeep::performUpKeep() should unregister pending market orders or disable triggers and pending limit orders if the execution fails.

However, it is not dealing with all the revert scenarios, for example:

1. Not enough value to [pay](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPriceUpKeep.sol#L126>) for the verifier.
2. [Invalid prices](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPriceUpKeep.sol#L147-L152>).

## Proof of Concept

No PoC provided.

## Recommendation

If performUpKeep() reverts due to one of these reasons, the protocol should be protected and make users pay for it. If it does not have enough value to pay for the verifier or the prices are invalid, the corresponding user should still pay the oracle fees.

Additionally, before calling [OstiumPriceUpKeep::getPrice()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPriceUpKeep.sol#L66>), a check should be in place to ensure the contract will have enough eth to pay for [performUpkeep()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPriceUpKeep.sol#L103>).

Instead of reverting, it should also unregister the orders and the triggers to allow faster replayability.
