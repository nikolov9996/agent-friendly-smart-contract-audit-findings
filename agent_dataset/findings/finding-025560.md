---
id: 25560
severity: "Medium"
---

# updatePair() is missing the pairOk() modifier

## Description

[OstiumPairsStorage::updatePair()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairsStorage.sol#L139>) updates a pair's attribute but does not check the new values.

## Proof of Concept

No PoC provided.

## Recommendation

Add the [pairOk()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairsStorage.sol#L78>) modifier to updatePair().
