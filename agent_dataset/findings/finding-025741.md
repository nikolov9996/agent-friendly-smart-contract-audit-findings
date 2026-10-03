---
id: 25741
severity: "Low/Info"
---

# txType == TransactionType.ExecuteSlowMode may cause batch of transactions to fail due to _slowModeConfig.txUpTo < _slowModeConfig.txCount

## Description

txType == TransactionType.ExecuteSlowMode allows the sequencer to execute slow mode transactions. However, these transactions can also be executed permissionlessly.

Endpoint::_executeSlowModeTransaction reverts if _slowModeConfig.txUpTo < _slowModeConfig.txCount, which means that if before executing Endpoint::submitTransactionsChecked(), someone executes the slow mode transactions up to the latest, the whole batch will revert.

## Proof of Concept

No PoC provided.

## Recommendation

This is unlikely to happen as there is a significant delay in slow mode transactions, which is ignored by the sequencer. Nontheless, an early return can be performed instead of reverting in Endpoint::_executeSlowModeTransaction.
