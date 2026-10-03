---
id: 25383
severity: "Low/Info"
---

# genesisMint gas costs can be reduced by caching genesisCounter

## Description

The [genesisMint()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L76-L80>) function could cache genesisCounter while looping:

```solidity
uint256 cachedGenesisCounter = genesisCounter;
for (uint i; i < _to.length; ++i) {
    _mint(_to[i], _ids[i]);
    isGenesis[_ids[i]] = true;
    cachedGenesisCounter++;
}
genesisCounter = cachedGenesisCounter;
```

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
