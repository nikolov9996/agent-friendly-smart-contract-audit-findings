---
id: 25207
severity: "Low/Info"
---

# _crossTransfer(...) should revert if users specify routerByDomain[destDomain] as destination

## Description

This scenario only happens if the router in the destDomain has the same address as the router in the destDomain. Else, the beneficiary check will fail. _crossTransfer(...) enables users to bridge assets to any destination, without calldata.

If users want to send assets to the router on the other chain, they might select _crossTransfer(...) instead of _crossTransferWithCalldata(...), which would cause them to lose their funds.

## Proof of Concept

No PoC provided.

## Recommendation

Add the check if (receiver) == routerByDomain[destDomain]) revert(); in the crossTransfer() call.
