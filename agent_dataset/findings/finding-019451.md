---
id: 19451
severity: "High"
---

# When `withdrawalBatchDuration` is set to zero lenders can withdraw more then allocated to a batch

## Description

The Wildcat protocol utilizes a withdrawal cycle where lenders call `queueWithdrawals` which then goes through a set amount of time (withdrawal duration period) before a withdrawal can be executed (if the protocol has enough funds to cover the withdrawal). Withdrawal requests that could not be fully honored at the end of their withdrawal cycle are batched together, marked as expired withdrawals, and added to the withdrawal queue. These batches are tracked using the time of expiry, and when assets are returned to a market with a non-zero withdrawal queue, assets are immediately routed to the unclaimed withdrawals pool and can subsequently be claimed by lenders with the oldest expired withdrawals first.

The `withdrawalBatchDuration` can be set to zero so lenders do not have to wait before being able to withdraw funds from the market; however, this can cause issues where lenders in a batch can withdraw more than their pro-rata share of the batch’s paid assets.

A lender calls `queueWithdrawal` first to initiate the withdrawal; this will place it in a batch respective to its expiry:
```solidity
    function queueWithdrawal(uint256 amount) external nonReentrant {
        MarketState memory state = _getUpdatedState();

        ...

        // If there is no pending withdrawal batch, create a new one.
        if (state.pendingWithdrawalExpiry == 0) {
            state.pendingWithdrawalExpiry = uint32(block.timestamp + withdrawalBatchDuration);
            emit WithdrawalBatchCreated(state.pendingWithdrawalExpiry);
        }
        // Cache batch expiry on the stack for gas savings.
        uint32 expiry = state.pendingWithdrawalExpiry;

        WithdrawalBatch memory batch = _withdrawalData.batches[expiry];

        // Add scaled withdrawal amount to account withdrawal status, withdrawal batch and market state.
        _withdrawalData.accountStatuses[expiry][msg.sender].scaledAmount += scaledAmount;
        batch.scaledTotalAmount += scaledAmount;
        state.scaledPendingWithdrawals += scaledAmount;

        emit WithdrawalQueued(expiry, msg.sender, scaledAmount);

        // Burn as much of the withdrawal batch as possible with available liquidity.
        uint256 availableLiquidity = batch.availableLiquidityForPendingBatch(state, totalAssets());
        if (availableLiquidity > 0) {
            _applyWithdrawalBatchPayment(batch, state, expiry, availableLiquidity);
        }

        // Update stored batch data
        _withdrawalData.batches[expiry] = batch;

        // Update stored state
        _writeState(state);
    }
```
Now once the `withdrawalBatchDuration` has passed, a lender can call `executeWithdrawal` to finalize the withdrawal. This will grab the batch and let the lender withdraw a percentage of the batch if the batch is not fully paid or all funds if it is fully paid.
```solidity
    function executeWithdrawal(address accountAddress, uint32 expiry) external nonReentrant returns (uint256) {
        if (expiry > block.timestamp) {
            revert WithdrawalBatchNotExpired();
        }
        MarketState memory state = _getUpdatedState();

        WithdrawalBatch memory batch = _withdrawalData.batches[expiry];
        AccountWithdrawalStatus storage status = _withdrawalData.accountStatuses[expiry][accountAddress];

        uint128 newTotalWithdrawn =
            uint128(MathUtils.mulDiv(batch.normalizedAmountPaid, status.scaledAmount, batch.scaledTotalAmount));
        uint128 normalizedAmountWithdrawn = newTotalWithdrawn - status.normalizedAmountWithdrawn;
        status.normalizedAmountWithdrawn = newTotalWithdrawn;
        state.normalizedUnclaimedWithdrawals -= normalizedAmountWithdrawn;

        ...

        // Update stored state
        _writeState(state);

        return normalizedAmountWithdrawn;
    }
```
Let’s look at how this percentage is determined: the `newTotalWithdrawn` function determines a lender’s available withdrawal amount by multiplying the `normalizedAmountPaid` with the `scaledAmount` and dividing the result by the batch’s `scaledTotalAmount`. This ensures that each lender in the batch can withdraw an even amount of the available funds in the batch depending on their `scaledAmount`.
```solidity
    uint128 newTotalWithdrawn =
        uint128(MathUtils.mulDiv(batch.normalizedAmountPaid, status.scaledAmount, batch.scaledTotalAmount));
```
This works fine when `withdrawalBatchDuration` is set over zero, as the batch values (except `normalizedAmountPaid`) are finalized. However, when set to zero, we can end up with lenders in a batch being able to withdraw more than `normalizedAmountPaid` in that batch, potentially violating protocol invariants.

Consider the following scenario:

There is only 5 tokens available to burn.

Lender A calls `queueWithdrawal` with 5 and `executeWithdrawal` instantly.
```solidity
    newTotalWithdrawn = (normalizedAmountPaid) * (scaledAmount) / scaledTotalAmount
    newTotalWithdrawn = 5 * 5 = 25 / 5 = 5
```
Lender A was able to fully withdraw.

Lender B comes along and calls `queueWithdrawal` with 5 and `executeWithdrawal` instantly in the same block. This will add to the same batch as lender A as it is the same expiry.

Now let’s look at `newTotalWithdrawn` for Lender B:
```solidity
    newTotalWithdrawn = (normalizedAmountPaid) * (scaledAmount) / scaledTotalAmount
    newTotalWithdrawn = 5 * 5 = 25 / 10 = 2.5
```
Lets see what the batch looks like now:

  * Lender A was able to withdraw 5 tokens in the batch.
  * Lender B was able to withdraw 2.5 tokens in the batch.
  * The `batch.normalizedAmountPaid` is 5, meaning the Lenders’ withdrawal amount surpassed the batch’s current limit.

This will break the following invariant in the protocol:

“Withdrawal execution can only transfer assets that have been counted as paid assets in the corresponding batch, i.e. lenders with withdrawal requests can not withdraw more than their pro-rata share of the batch’s paid assets.”

It will also mean that funds reserved for other batches may not be able to be fulfilled even if the batch’s `normalizedAmountPaid` number shows that it should be able to.

## Proof of Concept

no poc

## Recommendation

Review the protocol’s withdrawal mechanism and consider adjusting the behaviour of withdrawals when `withdrawalBatchDuration` is set to zero to ensure that lenders cannot withdraw more than their pro-rata share of the batch’s paid assets.

Thank you! Good catch - going to fix this by changing the assertion in `executeWithdrawal` from:
```solidity
    if (expiry > block.timestamp) {
        revert WithdrawalBatchNotExpired();
    }
```
to:
```solidity
    if (expiry >= block.timestamp) {
        revert WithdrawalBatchNotExpired();
    }
```
so that it’s guaranteed the withdrawal batch can not be added to when it’s in a state that allows execution.

Mitigated [here](https://github.com/wildcat-finance/wildcat-protocol/pull/57/commits/f9ecf3df04a6c9608faeae76f2c40d61716e9061).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the Wildcat protocol handles withdrawal batches when the configuration parameter withdrawalBatchDuration is set to zero. In normal operation a non‑zero duration creates a time window during which a batch’s accounting fields – especially the normalizedAmountPaid that represents the total assets actually paid out for the batch – are frozen before any lender can execute a withdrawal. When the duration is forced to zero, the batch expires immediately and lenders are allowed to call queueWithdrawal and executeWithdrawal in the same block. Because the contract updates the batch’s scaledTotalAmount before it finalises the normalizedAmountPaid, a second lender that joins the same expiry can calculate its withdrawable amount using the original normalizedAmountPaid (which only reflects the first lender’s payout) while the denominator of the pro‑rata formula now includes the combined scaled amounts of both lenders. The formula newTotalWithdrawn = normalizedAmountPaid * scaledAmount / scaledTotalAmount therefore yields a value that, when summed across all lenders in the batch, can exceed the actual paid assets. An attacker can submit multiple withdrawal requests in a single block, each receiving a share of the batch that together surpasses the batch’s paid balance, effectively creating an over‑withdrawal condition. The impact is a breach of a core protocol invariant – that withdrawals may not exceed the assets counted as paid for the batch – which can lead to funds disappearing from the market, other pending batches becoming under‑funded, and ultimately a loss of confidence in the protocol’s accounting integrity. This bug only manifests when withdrawalBatchDuration is zero and multiple withdrawals share the same expiry timestamp, affecting any lender using the market and the protocol’s overall liquidity pool. It was discovered during a security audit that examined edge‑case parameter settings and identified that the existing expiry check (if expiry > block.timestamp) allowed immediate execution, missing the case where expiry equals the current block timestamp. The issue is subtle because the same code works correctly for typical non‑zero durations, so the over‑withdrawal scenario is not obvious during routine testing. To remediate the problem the contract should prevent execution when expiry is equal to the current timestamp (changing the check to expiry >= block.timestamp) or disallow a zero‑duration configuration altogether, and ensure that the normalizedAmountPaid is updated atomically with respect to the scaledTotalAmount before any withdrawal calculation is performed, thereby guaranteeing that each lender can only withdraw their true pro‑rata share of the batch’s paid assets.
