---
id: 23335
severity: "Critical"
---

# cancelling redeem requests permanently blocks the withdrawal queue

## Description

AccountableWithdrawalQueue can deadlock at the head if the current head entry (_queue.nextRequestId) is fully removed (e.g., by a cancel that zeroes shares and clears controller) without advancing nextRequestId.  

In `AccountableWithdrawalQueue::_processUpToShares` and `AccountableWithdrawalQueue::_processUpToRequestId`, the loop checks if `(shares_ == 0) break;` before incrementing `nextRequestId`:

```solidity
(uint256 shares_, uint256 assets_, bool processed_) =
    _processRequest(request_, liquidity, maxShares_, precision_);
if (shares_ == 0) break;
```

When the head is an empty entry (`controller == address(0)`), `AccountableWithdrawalQueue::_processRequest` returns `(0, 0, true)`, `shares_ == 0`, the loop breaks:

```solidity
if (request.controller == address(0)) return (0, 0, true);
```

The head never advances, so every subsequent call to process or preview gets stuck on the same empty head forever.

This can be triggered by any user whose request is currently at the head by canceling any dust amount (even 1 wei) such that their head entry is fully deleted at the time of processing (e.g., instant cancel‑fulfillment) in `AccountableWithdrawalQueue::_delete`:

```solidity
/// @dev Deletes a withdrawal request and its controller from the queue
function _delete(address controller, uint128 requestId) private {
    delete _queue.requests[requestId];
    delete _requestIds[controller];
}
```

Once the head becomes an empty slot and the pointer doesn’t move, the entire queue is bricked.

**Impact:** Queue is permanently stuck and no subsequent user will be able to withdraw.

## Proof of Concept

Add the following test to `test/vault/AccountableWithdrawalQueue.t.sol`:

```solidity
function testHeadDeletionDeadlocksQueue() public {
    // Setup: deposits are instant, redemptions are queued, cancel is instantly fulfilled
    strategy.setInstantFulfillDeposit(true);
    strategy.setInstantFulfillRedeem(false);
    strategy.setInstantFulfillCancelRedeem(true);
    // Seed vault with liquidity and create first (head) request by Alice
    // This helper deposits for Alice and Bob at 1e36 price.
    _setupInitialDeposits(1e36, DEPOSIT_AMOUNT);
    // 1) Alice creates a redeem request -> head of queue (requestId = 1)
    uint256 aliceSharesToQueue = 1;
    vm.prank(alice);
    uint256 headId = vault.requestRedeem(aliceSharesToQueue, alice, alice);
    assertEq(headId, 1, "first request should be head (id = 1)");
    // 2) Alice cancels; cancel is fulfilled instantly by the strategy.
    // This fully removes the head request entry (controller becomes address(0)),
    // but _queue.nextRequestId is NOT advanced by the implementation.
    vm.prank(alice);
    vault.cancelRedeemRequest(headId, alice);
    // Sanity: queue indices should still point at the deleted head
    (uint128 nextRequestId, uint128 lastRequestId) = vault.queue();
    assertEq(nextRequestId, 1, "nextRequestId remains stuck at deleted head");
    assertGe(lastRequestId, 1, "there is at least one request in the queue history");
    // 3) Charlie makes a NEW redeem request -> tail (requestId = 2).
    // This request is perfectly processable with existing liquidity.
    token.mint(charlie, 1000e6);
    vm.prank(charlie);
    token.approve(address(vault), 1000e6);
    vm.prank(charlie);
    vault.deposit(1000e6, charlie);
    uint256 charlieShares = vault.balanceOf(charlie) / 2;
    vm.prank(charlie);
    uint256 tailId = vault.requestRedeem(charlieShares, charlie, charlie);
    assertEq(tailId, 2, "second request should be tail (id = 2)");
    // Check queue bounds reflect head(=1, deleted) and tail(=2, valid)
    (nextRequestId, lastRequestId) = vault.queue();
    assertEq(nextRequestId, 1, "still pointing at deleted head");
    assertEq(lastRequestId, 2, "tail id should be 2");
    // 4) Attempt to process. BUG: _processUpToShares reads head slot (controller==0),
    // inner _processRequest returns (0,0,true), outer loop sees shares_==0 and BREAKS
    // BEFORE ++nextRequestId, so NOTHING gets processed and the queue is permanently stuck.
    uint256 assetsBefore = vault.totalAssets();
    uint256 used = vault.processUpToShares(type(uint256).max);
    assertEq(used, 0, "deadlock: processing does nothing while a valid tail exists");
    (uint256 _shares, uint256 _assets) = vault.processUpToRequestId(2);
    assertEq(_shares, 0, "deadlock: processing does nothing while a valid tail exists");
    assertEq(_assets, 0, "deadlock: processing does nothing while a valid tail exists");
    // 5) Verify tail wasn't progressed at all
    assertEq(vault.claimableRedeemRequest(0, charlie), 0, "tail remains unclaimable");
    assertEq(vault.pendingRedeemRequest(0, charlie), charlieShares, "tail remains fully pending");
    assertEq(vault.totalAssets(), assetsBefore, "no reserves changed due to deadlock");
    (nextRequestId, lastRequestId) = vault.queue();
    assertEq(nextRequestId, 1, "nextRequestId is still stuck at deleted head");
}
```

## Recommendation

Recommended Mitigation: Consider incrementing the counter if it’s processed, and continue instead of break:

```solidity
if (shares_ == 0) {
    if (processed_) {
        ++nextRequestId;
        continue;
    }
    break;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a deadlock in the AccountableWithdrawalQueue used for handling redeem requests. When the request at the front of the queue (the head) is cancelled, the contract deletes the request entry and clears its controller address. The internal processing functions (_processUpToShares and _processUpToRequestId) iterate over the queue and stop as soon as a request returns zero shares. For an empty head entry the _processRequest routine returns (0, 0, true). Because the loop checks \"if (shares == 0) break\" before incrementing the nextRequestId pointer, the head index never advances. Consequently the queue remains stuck on the empty slot forever, and any subsequent redeem requests, even those with sufficient liquidity, are never processed. The bug can be triggered by any user whose request is currently at the head by cancelling even a minimal amount, such as 1 wei, which fully removes the head entry. The impact is that the withdrawal queue becomes permanently blocked, preventing all users from withdrawing their funds; balances appear unchanged and users may see that their pending redeem requests never become claimable. The condition occurs only when the head request is deleted while the processing loop is invoked; under normal operation where the head remains populated, the queue works as intended. The issue was discovered during a security audit through a targeted test that cancelled the head request and then attempted to process the queue, observing that processUpToShares and processUpToRequestId returned zero and the nextRequestId stayed at the deleted entry. The bug is subtle because the contract correctly records new requests and the queue data structures appear intact, making the deadlock hard to notice without explicit testing of the head‑cancellation scenario. It belongs to the class of logical queue‑management errors where pointer advancement is omitted for empty entries, leading to a permanent stall. From a user’s perspective the symptoms are a missing withdrawal, a UI that shows pending requests never moving to a claimable state, and balances that remain static despite new deposits. The expected behavior is that a cancelled request should be removed and the queue should continue processing the next request, but the reality is that the queue pointer does not move, violating the protocol’s accounting assumptions. The recommended mitigation is to modify the processing loop so that when a request returns zero shares but is marked as processed, the contract increments nextRequestId and continues iterating instead of breaking. This change ensures that empty slots are skipped and the queue can progress, restoring normal withdrawal functionality without altering the external API.
