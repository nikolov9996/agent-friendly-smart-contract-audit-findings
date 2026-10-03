---
id: 25722
severity: "Medium"
---

# Missing disableInitializers() call in the constructor

## Description

When using Initializable.sol, it's a good practice calling disableInitializers() in the constructor, such that the implementation itself can't be initialized.

The call is missing in the [Clearinghouse.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/contracts/Clearinghouse.sol>), [Endpoint.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/contracts/Endpoint.sol>), [OffchainExchange.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/contracts/OffchainExchange.sol>), [PerpEngine.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/contracts/PerpEngine.sol>), [SpotEngine.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/contracts/SpotEngine.sol>), [ClearinghouseLiq.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/contracts/ClearinghouseLiq.sol>) and [Verifier.sol](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/contracts/Verifier.sol>) (commented out).

ClearingHouse may be selfdestructed via the [delegateCall()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/Clearinghouse.sol#L480-L482>).

## Proof of Concept

No PoC provided.

## Recommendation

Use:

```solidity
constructor() {
    _disableInitializers();
}
```
