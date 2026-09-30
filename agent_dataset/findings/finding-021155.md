---
id: 21155
severity: "High"
---

# `deployWithdrawalQueue`

## Description

In `deployWithdrawalQueue()`, only clears `_queueOutstandingValues[lastQueueIndex]` and `_outstandingValues`, but doesn’t clear `_queueAccounting[lastQueueIndex]`.
```solidity
function deployWithdrawalQueue() external nonReentrant {
    ...

    /// @dev We move outstanding values from the pool to the queue that was just deployed.
    _queueOutstandingValues[pendingQueueIndex] = _outstandingValues;
    /// @dev We clear values of the new pending queue.
    delete _queueOutstandingValues[lastQueueIndex];
    delete _outstandingValues;
    //@audit miss delete _queueAccounting[lastQueueIndex]

    _updateLoanLastIds();

    _pendingQueueIndex = lastQueueIndex;

    // Cannot underflow because the sum of all withdrawals is never larger than totalSupply.
    unchecked {
        totalSupply -= sharesPendingWithdrawal;
    }
}
```
After this method, anyone calling `queueClaimAll()` will use this stale data `_queueAccounting[lastQueueIndex]`.

`queueClaimAll()` -> `_queueClaimAll(_pendingQueueIndex)`-> `_updatePendingWithdrawalWithQueue(_pendingQueueIndex)`
```solidity
function _updatePendingWithdrawalWithQueue(
    uint256 _idx,
    uint256 _cachedPendingQueueIndex,
    uint256[] memory _pendingWithdrawal
) private returns (uint256[] memory) {
    uint256 totalReceived = getTotalReceived[_idx];
    uint256 totalQueues = getMaxTotalWithdrawalQueues + 1;
    /// @dev Nothing to be returned
    if (totalReceived == 0) {
        return _pendingWithdrawal;
    }
    getTotalReceived[_idx] = 0;

    /// @dev We go from idx to newer queues. Each getTotalReceived is the total
    /// returned from loans for that queue. All future queues/pool also have a piece of it.
    /// X_i: Total received for queue `i`
    /// X_1  = Received * shares_1 / totalShares_1
    /// X_2 = (Received - (X_1)) * shares_2 / totalShares_2 ...
    /// Remainder goes to the pool.
    for (uint256 i; i < totalQueues;) {
        uint256 secondIdx = (_idx + i) % totalQueues;
        QueueAccounting memory queueAccounting = _queueAccounting[secondIdx];
        if (queueAccounting.thisQueueFraction == 0) {
            unchecked {
                ++i;
            }
            continue;
        }
        /// @dev We looped around.
        if (secondIdx == _cachedPendingQueueIndex + 1) {
            break;
        }
        uint256 pendingForQueue = totalReceived.mulDivDown(queueAccounting.thisQueueFraction, PRINCIPAL_PRECISION);
        totalReceived -= pendingForQueue;

        _pendingWithdrawal[secondIdx] = pendingForQueue;
        unchecked {
            ++i;
        }
    }
    return _pendingWithdrawal;
}
```

## Proof of Concept

no poc

## Recommendation

```solidity
function deployWithdrawalQueue() external nonReentrant {
    ...

    /// @dev We move outstaning values from the pool to the queue that was just deployed.
    _queueOutstandingValues[pendingQueueIndex] = _outstandingValues;
    /// @dev We clear values of the new pending queue.
    delete _queueOutstandingValues[lastQueueIndex];
    delete _queueAccounting[lastQueueIndex];
    delete _outstandingValues;

    _updateLoanLastIds();

    _pendingQueueIndex = lastQueueIndex;

    // Cannot underflow because the sum of all withdrawals is never larger than totalSupply.
    unchecked {
        totalSupply -= sharesPendingWithdrawal;
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incomplete state cleanup in the function that deploys a new withdrawal queue. After moving the outstanding values from the pool to the newly created queue, the implementation deletes the mapping entry that stores the outstanding values for the previous queue and clears the temporary outstanding values variable, but it forgets to delete the accounting record associated with the previous queue. This accounting record (often a struct containing the fraction of the queue that should receive funds) remains in storage with stale data. When a user later calls the function that claims all pending withdrawals, the claim logic reads the stale accounting entry because the index of the previous queue is still referenced as the pending queue index. The stale fraction is then used in the proportional calculation that distributes received loan repayments across queues. As a result, the contract may allocate an incorrect amount to the caller – either granting more funds than entitled or leaving other participants with less than expected. The bug manifests only after a new queue has been deployed and a claim is performed before the stale accounting entry is overwritten, which is a subtle condition that can be missed by basic testing. It affects any participant who attempts to withdraw, potentially leading to loss of funds for honest users or unintended profit for an attacker who can orchestrate the sequence of calls. The issue was discovered during a formal audit where the reviewer noted the missing delete statement. It is hard to notice because the function appears to clear the relevant values, and the leftover accounting data does not cause an immediate revert; instead it silently skews the accounting math. Conceptually, the bug belongs to the class of “incomplete state reset” or “stale storage reference” vulnerabilities, where residual data from a previous epoch contaminates the current epoch’s calculations. From a user’s perspective the UI may show a normal withdrawal request but the received amount may be zero, unexpectedly high, or simply not match the expected share, violating the protocol’s guarantee that each user receives a proportionate refund. The proper fix is to ensure that the accounting mapping entry for the previous queue is also cleared (e.g., using delete on the mapping entry) when the new queue is deployed, thereby guaranteeing that no stale fractions are used in subsequent withdrawal calculations.
