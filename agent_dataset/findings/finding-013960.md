---
id: 13960
severity: "High"
---

# assets > withdrawableWei() check in _decreaseBalance() could DOS NativeVault._updateSnapshot()

## Description

Whenever a snapshot is completed, NativeVault._updateSnapshot() calls to update the node owner's balance:
```solidity
_updateBalance(nodeOwner, totalDeltaWei);
```
If totalDeltaWei happens to be negative, _updateBalance() calls _decreaseBalance(), which checks that totalDeltaWei is not greater than withdrawableWei():
```solidity
if (assets > withdrawableWei(_of)) revert WithdrawMoreThanMax();
```
Note that withdrawableWei() returns the minimum between the node owner's native node balance and the assets equivalent of his shares.
However, this check could cause _updateSnapshot() to incorrectly revert when completing a snapshot. For example:
• Assume a node owner has 32 ETH in a validator and no ETH in his native node.
• The following events occur:
– His native node receives 0.3 ETH from validator rewards.
– The beacon chain slashes his validator for 1 ETH, leaving 31 ETH remaining.
• He calls startSnapshot(), which sets nodeBalanceWei = 0.3 ether as his native node gained 0.3 ETH.
• He calls validateSnapshotProofs(), which sets balanceDeltaWei = -1 ether as his validator lost 1 ETH.
• When _updateSnapshot() is called:
– totalDeltaWei = 0.3 ether - 1 ether = -0.7 ether
– _decreaseBalance() is called with assets = 0.7 ether.
– withdrawableWei() returns his native node's balance, which is 0.3 ETH.
– Since assets > withdrawableWei(), the function reverts.
As seen from above, if a node owner's validators are slashed for more than his native node's current balance, _updateSnapshot() will always revert when called. This makes it impossible to update his snapshot, even after it expires.

## Proof of Concept

no poc

## Recommendation

Consider removing the assets > withdrawableWei(_of) check from _decreaseBalance():
```solidity
function _decreaseBalance(address _of, uint256 assets) internal {
NativeVaultLib.Storage storage self = _state();
if (assets > withdrawableWei(_of)) revert WithdrawMoreThanMax();
```
This check should be moved into finishWithdrawal() instead to ensure the user cannot withdraw assets than he should be able to.

## Derived Narrative

The following field is derived content and may not be source-grounded:

During a snapshot, NativeVault._updateSnapshot calls _updateBalance with the net change totalDeltaWei. If totalDeltaWei is negative, the internal function _decreaseBalance is invoked. _decreaseBalance contains a guard that compares the amount to be decreased (assets) with withdrawableWei(_of) and reverts if assets is larger. withdrawableWei returns the smaller of the node owner's native balance and the value of his shares. This guard is appropriate for user‑initiated withdrawals, but it is incorrectly reused for internal balance adjustments that represent a loss of validator stake. When a validator is slashed by an amount greater than the native node's current balance, the negative delta exceeds withdrawableWei, causing the guard to trigger and the whole snapshot update to revert. The revert prevents the snapshot from being finalized, even after its expiration, effectively locking the node owner's balance updates and making further withdrawals impossible. The issue appears only when the slash magnitude surpasses the native node's accumulated rewards, so it is not obvious during normal operation. It was discovered during a manual audit of the snapshot logic, where the auditor traced the call chain and observed that the revert condition could be satisfied with realistic numbers. From a user perspective the UI reports a transaction failure or an 'update snapshot' error, and the expected balance change never occurs, leading to confusion and a perception that funds have disappeared. The vulnerability belongs to the class of 'incorrect reuse of withdrawal limits in internal accounting', a form of denial‑of‑service where business logic that should allow negative adjustments is blocked by a withdrawal‑only check. To remediate, the assets > withdrawableWei check should be removed from _decreaseBalance and relocated to the public finishWithdrawal path, where the restriction is meaningful. This change allows snapshot updates to apply negative deltas regardless of the current withdrawable amount, while still protecting users from withdrawing more than they are entitled to.
