---
id: 25208
severity: "Low/Info"
---

# When transferring tokens, if the amount is 0, the transfer should be skipped

## Description

Before each transfer call, if the amount is 0, it should be skipped. This is also true for SafeERC20.safeTransfer(...) and SafeERC20.safeTransferFrom(...).

## Proof of Concept

No PoC provided.

## Recommendation

An example would be

```solidity
function _safeTransferETH(address receiver, uint256 amount) internal {
    if (amount == 0) return;
    (bool success,) = receiver.call{value: amount}(new bytes(0));
    if (!success) revert BaseRouter__safeTransferETH_transferFailed();
}
```
