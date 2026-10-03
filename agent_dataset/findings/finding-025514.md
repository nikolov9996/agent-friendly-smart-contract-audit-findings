---
id: 25514
severity: "Low/Info"
---

# OstiumTradingCallbacks::executeAutomationOpenOrderCallback() reverts if it can not find the openLimitOrder

## Description

[OstiumTradingCallbacks::executeAutomationOpenOrderCallback()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingCallbacks.sol#L256>) fetches the openLimitOrder before checking for its [existence](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumTradingStorage.sol#L437>), which will end up reverting if it does not exist, not finishing execution.

## Proof of Concept

No PoC provided.

## Recommendation

Check the existence of the limit order before fetching it.
