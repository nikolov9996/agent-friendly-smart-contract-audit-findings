---
id: 25725
severity: "Low/Info"
---

# Unused argument in Endpoint::registerTransferableWallet()

## Description

Endpoint::registerTransferableWallet() sets transferableWallets[wallet] to true, [but](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/Endpoint.sol#L838-L843>) a _transferable argument can be provided.

## Proof of Concept

No PoC provided.

## Recommendation

Delete the argument or replace true by _transferable.
