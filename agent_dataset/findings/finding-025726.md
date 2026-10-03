---
id: 25726
severity: "Low/Info"
---

# isHealthy() Function Always Returns True

## Description

The [isHealthy](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/4286c37cf4ee59d7e3231ac4683859f54d0d8e96/contracts/OffchainExchange.sol#L584-L588>) function in OffchainExchange.sol consistently returns true regardless of its parameter.

## Proof of Concept

No PoC provided.

## Recommendation

While the function is marked as virtual, there are currently no contracts inheriting and overriding OffchainExchange.sol. Consider adding meaningful implementation.
