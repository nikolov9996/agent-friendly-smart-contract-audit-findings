---
id: 25519
severity: "Low/Info"
---

# updateGroupCollateral() should revert if the _pairIndex does not exist

## Description

[OstiumPairsStorage::updateGroupCollateral()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumPairsStorage.sol#L186>) does not check for the pair's index existence, which means that it would update group with index 0 incorrectly.

## Proof of Concept

No PoC provided.

## Recommendation

Add if (!isPairIndexListed[_pairIndex]) revert PairNotListed(_pairIndex); to the function.
