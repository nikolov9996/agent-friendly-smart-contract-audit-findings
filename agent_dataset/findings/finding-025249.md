---
id: 25249
severity: "Low/Info"
---

# Usage of transferFrom() could revert if used from itself

## Description

Under normal circumstances the usage of transferFrom() in the function withdraw() in [AaveV3Strategy](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/ReservePool/strategies/AaveV3Strategy.sol#L81>) and in [GReservePool](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/ReservePool/GReservePool.sol#L207>) would revert as it would be necessary for the contract to approve itself.

When transferring its own funds it should use .call() instead. WAVAX does not revert in this instance but other tokens would.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
