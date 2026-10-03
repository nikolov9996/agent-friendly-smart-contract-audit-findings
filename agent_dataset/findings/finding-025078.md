---
id: 25078
severity: "Crit/High"
---

# Anyone can grief users, stopping them from fulfilling their withdrawals

## Description

On the Batch.sol contract, anyone can call [withdrawFulfill()](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/BatchOut.sol#L326>) with the current cycle id, incrementing the cycleInfo[currentCycleID].withdrawRequestsFullFilled and setting the userWithdrawStorage[cycleID][userAddress].withdrawStatus to true, without sending any tokens to the users, since the currentCycle.tokensWithdrawn.token will have a length of zero, so the loop will constantly skip iterations at this [continue](<https://github.com/ClipFinance/strategy-router/blob/master/contracts/BatchOut.sol#L357>).

When someone inevitably calls executeBatchWithdrawFromStrategyWithSwap() and then withdrawFulfill(), the loop will start with the offset cycleInfo[currentCycleID].withdrawRequestsFullFilled and some users will have the userWithdrawStorage[cycleID][userAddress].withdrawStatus flag set to true, so they will be skipped and will never be able to receive the tokens from their shares.

This issue is also problematic because, if later but still in the same cycle, the same users try to add shares, they will be added to the previous request (which will always be skipped by the withdrawFulfill()), so they will also lose these extra shares.

## Proof of Concept

No PoC provided.

## Recommendation

Add require(cycleID < currentCycleId); at the start of withdrawFulfill().
