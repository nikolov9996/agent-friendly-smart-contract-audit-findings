---
id: 25427
severity: "Low/Info"
---

# BasicVault::_resolveWithIdleBalance() can return before calculating _idleBalance() to save gas

## Description

BasicVault::_resolveWithIdleBalance() returns when there is enough reserved amount to fulfill all requests. In this case, there is no need to fetch the _idleBalance(), should the order should be inverted to save gas.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
function _resolveWithIdleBalance(StorageV2 storage $v2, IERC20 asset_)
internal returns (uint256 resolved) {
    uint256 remaining = $v2.redeemQueue.remaining();
    if (remaining == 0) return 0;
    uint256 idleBalance_ = _idleBalance($v2, asset_);
    resolved = remaining > idleBalance_ ? idleBalance_ : remaining;
    $v2.redeemQueue.reserve(resolved);
    return resolved;
}
```
