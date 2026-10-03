---
id: 25310
severity: "Low/Info"
---

# Queue MapleWithdrawalManager may revert due to honest removeShares() or manual redeem calls

## Description

The queue withdrawal manager [limits](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/749a035a3531c10d7e5d9b84af2a1115d78880b2/contracts/MapleWithdrawalManager.sol#L172>) the sharesToProcess in processRedemptions() to the totalShares.

This might make the call revert if non malicious users [remove](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/749a035a3531c10d7e5d9b84af2a1115d78880b2/contracts/MapleWithdrawalManager.sol#L210>) shares or do [manual](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/749a035a3531c10d7e5d9b84af2a1115d78880b2/contracts/MapleWithdrawalManager.sol#L293>) redeems.

Another concurrency issue is if the available liquidity is just enough to cover for a processRedemptions() call, but someone frontruns it and does a manual redeem.

## Proof of Concept

No PoC provided.

## Recommendation

Instead of reverting if the processedShares argument is bigger than totalShares, limit it:

```solidity
function processRedemptions(uint256 sharesToProcess_) external override
whenProtocolNotPaused nonReentrant onlyRedeemer {
    ... uint256 cachedTotalShares_ = totalShares;
    if (sharesToProcess_ > cachedTotalShares_) sharesToProcess_ = cachedTotalShares_;
    ... }
```

It's trickier to solve the lack of liquidity concurrency issue, as it would require allowing [partial](<https://github.com/maple-labs/withdrawal-manager-queue-private/blob/v1.0.0-rc.0/contracts/MapleWithdrawalManager.sol#L172>) redemptions.
