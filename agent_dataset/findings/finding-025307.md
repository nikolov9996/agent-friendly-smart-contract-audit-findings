---
id: 25307
severity: "Low/Info"
---

# Gas savings

## Description

Queue MapleWithdrawalManager: In [_processRequest()](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/749a035a3531c10d7e5d9b84af2a1115d78880b2/contracts/MapleWithdrawalManager.sol#L321>), queue.requests[requestId_].shares -= processedShares_; can be replaced by queue.requests[requestId_].shares = request_.shares processedShares_; to avoid reading 1 storage slot.

Additionally, the line can be moved to the next [else](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/749a035a3531c10d7e5d9b84af2a1115d78880b2/contracts/MapleWithdrawalManager.sol#L330>) statement, to avoid writing 0 in the slot twice (subtracting and ending up with 0 and then deleting).

Similarly to what is done in [_removeShares()](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/749a035a3531c10d7e5d9b84af2a1115d78880b2/contracts/MapleWithdrawalManager.sol#L216>).

The subtraction on [line 168](<https://github.com/maple-labs/withdrawal-manager-cyclical-private/blob/v1.1.0-rc.0/contracts/MapleWithdrawalManager.sol#L168>) of the MapleWithdrawalManager should only be performed if lockedShares != 0.

This would prevent a storage read and write when lockedShares == 0, which seems the most likely scenario when calling addShares(). Recommendation: if (lockedShares_ != 0){ totalCycleShares[exitCycleId_] -= lockedShares_;} Still on the cyclical withdrawal manager, [line 250](<https://github.com/maple-labs/withdrawal-manager-cyclical-private/blob/v1.1.0-rc.0/contracts/MapleWithdrawalManager.sol#L250>), the partialLiquidity check will always return true, since if (new)lockedShares_ != 0 -> (old)lockedShares_ != redeemableShares_ -> partialLiquidity, this check can therefore be safely removed.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
