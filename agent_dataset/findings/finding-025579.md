---
id: 25579
severity: "Medium"
---

# Withdrawals can fail due to deposits reverting in completeQueuedWithdrawal()

## Description



## Proof of Concept

**Scenario A:**

1. The `nativeEthRestakeAdmin` queues a withdrawal for 10 ETH, 10 stETH and 10 wBETH.
2. After the withdrawal delay passes, `completeQueuedWithdrawal()` is called to process the withdrawals.
3. The 10 ETH are forwarded to the deposit queue.
4. Next, 9 stETH are withdrawn and sent to `WithdrawQueue`, filling its stETH buffer.
5. 1 stETH remains and is attempted to be deposited back into the stETH strategy via `strategyManager.depositIntoStrategy()`.
6. However, the stETH strategy has already reached its total deposit limit.
7. The deposit reverts and causes the entire `completeQueuedWithdrawal()` transaction to revert.

**Scenario B:**

1. A user calls `RestakeManager.deposit()` to deposit 1 wBETH.
2. All wBETH but 1 wei is used to fill the wBETH buffer in the `WithdrawQueue`.
3. The remaining 1 wei is then attempted to be deposited into the wBETH strategy via `strategyManager.depositIntoStrategy()`.
4. However, it is converted into `0` shares by the strategy.
5. `StrategyManager` verifies that the number of shares minted by the strategy is greater than `0`.
6. Since `0` shares were minted, this check fails.
7. The `strategyManager.depositIntoStrategy()` call reverts.
8. This causes the entire `RestakeManager.deposit()` transaction to revert due to no fault of the user's.

## Recommendation

Consider catching any reverts when depositing excess tokens into strategies. In order to ensure that the excess tokens remain in the system and are accounted for in the TVL, the best option may be to send them to the `WithdrawQueue` in the catch clause, regardless of whether the buffer for the given token is already full.
