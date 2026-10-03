---
id: 25418
severity: "Medium"
---

# BasicVault::_redeem() does not correctly deal with a disabled redeem queue after it was enabled

## Description

BasicVault::_redeem() only calls BasicVault::_resolveWithIdleBalance() when the redeem queue is enabled, but it should also do it when it is disabled as not enough assets may have been reserved.

Additionally, when the redeem queue is disabled, it only checks the balance of the contract, not the _idleBalance(), as amounts may have been reserved to fulfill requests.

## Proof of Concept

No PoC provided.

## Recommendation

```solidity
... _resolveWithIdleBalance($v2, asset_);
if ($v2.redeemQueueEnabled) {
    uint256 requestId = $v2.redeemQueue.push(_msgSender(), amount);
    emit RedeemQueued(receiver, address(asset_), requestId);
} else {
    if (_idleBalance($v2, asset_) < newAmount)
    revert("You're unable to redeem your assets now. Please try again later.");
    asset_.safeTransfer(receiver, newAmount);
}
...
```
