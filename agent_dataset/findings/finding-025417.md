---
id: 25417
severity: "Crit/High"
---

# BasicVault::_redeem() burns newAmount but redeems amount, allowing attackers to drain the vault

## Description

BasicVault::_redeem() is inconsistent as it burns newAmount, the value returned from the hook, but pushes a request to the redeem queue with amount.

As hook::reportRedeem() will cap the amount to redeem to the current load, the last user to withdraw may specify a huge amount to redeem, which will be capped to the remaining load, burning the capped newAmount shares, but pushing a request with the huge amount.

## Proof of Concept

No PoC provided.

## Recommendation

uint256 requestId = $v2.redeemQueue.push(_msgSender(), newAmount);
