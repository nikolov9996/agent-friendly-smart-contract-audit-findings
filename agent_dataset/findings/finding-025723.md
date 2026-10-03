---
id: 25723
severity: "Low/Info"
---

# Downcasting Leads to Silent Overflow

## Description

Variables of type int128 are being upcasted to int256 and then downcasted again in the burnLp function in [PerpEngineLp.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/PerpEngineLp.sol#L91-L98>) and [SpotEngineLP.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/SpotEngineLP.sol#L92-L97>), leading to silent overflow.

## Proof of Concept

No PoC provided.

## Recommendation

Consider using a solution like [OpenZeppelin's SafeCast Library](<https://docs.openzeppelin.com/contracts/3.x/api/utils#SafeCast>).
