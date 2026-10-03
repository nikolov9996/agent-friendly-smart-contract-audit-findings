---
id: 25176
severity: "Low/Info"
---

# _to argument missing 0x0 address check in the ConnextRouter

## Description

The ConnextRouter does not check, in the _crossTransfer(...) and _crossTransferWithCalldata(...) functions, if the receiver and routerByDomain[destDomain] equal address(0). This should revert anyway because the Connext contract reverts if _to is address(0), but it's safer to make this additional check.

## Proof of Concept

No PoC provided.

## Recommendation

Check if the address is 0.
