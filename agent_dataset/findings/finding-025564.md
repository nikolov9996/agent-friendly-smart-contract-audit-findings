---
id: 25564
severity: "Medium"
---

# The claimer's fee will be stolen by the winner

## Description



## Proof of Concept

## Vulnerability Detail

The user calls `claimPrizes` to collect prizes for the winner, thereby earning a reward fee.

Throughout the process, the winner can set hooks before and after calling `prizePool.claimPrize`. The winner can set an `afterClaimPrize` hook and then call `claimer.claimPrizes` again within this `afterClaimPrize` hook, thereby earning reward fees without using any gas. As a result, the user can only collect the reward fee for one winner, while the remaining reward fees for other winners will all be collected by the first winner.

Consider the following scenario:

1. User A calls `claimer.claimPrizes` to claim prizes, setting the winners as [B, C, D, E, F] (B, C, D, E, F are all winners).
2. User B notices in the mempool that User A is about to call `claimer.claimPrizes` to claim prizes for others. User B then calls `setHooks` to set the `afterClaimPrize` function, which implements a logic to loop call `claimer.claimPrizes` with winners set as [C, D, E, F].
3. User A's transaction is executed, but since User B has already claimed the rewards for C, D, E, and F, User A's attempts to claim prizes for C, D, E, and F will revert. However, due to the `try-catch`, User A's transaction will continue executing. In the end, User A will only receive the reward fee for User B.

This is essentially the same attack method as the previous PoolTogether vulnerability. The last audit did not completely fix it. The difference this time is that the hook uses `afterClaimPrize`.

[https://code4rena.com/reports/2024-03-pooltogether#m-01-the-winner-can-steal-claimer-fees-and-force-him-to-pay-for-the-gas](<https://code4rena.com/reports/2024-03-pooltogether#m-01-the-winner-can-steal-claimer-fees-and-force-him-to-pay-for-the-gas>)

## Impact

The user will lose the reward fee

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-vault/src/abstract/Claimable.sol#L110-L117](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-vault/src/abstract/Claimable.sol#L110-L117>)

## Recommendation

If the hook's purpose is for managing whitelists and blacklists, PoolTogether can create a template contract that users can manage. This way, the hook can only be set to the template contract and cannot perform additional operations.

If users are allowed to perform any operation, there is no good solution to this problem. The only options are to limit the gas, use reentrancy locks, or remove the after hook altogether.
