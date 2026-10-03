---
id: 25540
severity: "Low/Info"
---

# OstiumPairsStorage::getAllPairsMaxLeverage() reverts if enough pairs are created

## Description

[OstiumPairsStorage::getAllPairsMaxLeverage()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairsStorage.sol#L280>) reverts if enough pairs are created due to OOG.

## Proof of Concept

No PoC provided.

## Recommendation

Add an additional function OstiumPairsStorage::getAllPairsMaxLeverage(uint256 startId, uint256 finalId) to fetch paginated information.
