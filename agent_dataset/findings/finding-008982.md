---
id: 8982
severity: "High"
---

# Faulty deposit_for() check

## Description

The claim() function in the RewardsDistributor contract is designed to claim rewards for vePeg locks. It transfers rewards directly if the lock is expired or calls the vePeg.deposit_for() function if the lock is not expired or is perpetually locked:
```solidity
function claim(uint256 _tokenId) external returns (uint256) {
    //...
    if (amount != 0) {
        //...
        if (locked.end > block.timestamp || locked.perpetuallyLocked) {
            // lock has not expired
            ve.deposit_for(_tokenId, amount);
        } else {
            // lock expired
            address owner = ve.ownerOf(_tokenId);
            token.safeTransfer(owner, amount);
        }
        //...
    }
    //...
```
The issue arises with perpetual locks. The deposit_for() function checks if lock.end > block.timestamp, but for perpetual locks, the lock's end time is always set to zero, which is considered expired by the implemented check in the deposit_for() function. This causes the deposit_for() function to revert when attempting to deposit rewards for perpetual locks:
```solidity
function deposit_for(uint256 _tokenId, uint256 _value) external nonreentrant {
    LockedBalance memory _locked = locked[_tokenId];
    //...
    require(
        _locked.end > block.timestamp,
        "Cannot add to expired lock. Withdraw"
    );
    //...
```
As a result, perpetual locks cannot receive their rewards, preventing them from increasing their voting power by the amount claimed. The only workaround is for the owner to unlock the perpetual lock using the unlock_perpetual() function.

## Proof of Concept

No poc.

## Recommendation

Update the deposit_for() function to correctly handle perpetual locks by checking their status and updating the perpetuallyLockedBalance accordingly:
```solidity
function deposit_for(uint256 _tokenId, uint256 _value) external nonreentrant {
    LockedBalance memory _locked = locked[_tokenId];
    //...
    - require
    - (_locked.end > block.timestamp, "Cannot add to expired lock. Withdraw");
    + require
    + (_locked.end > block.timestamp || _locked.perpetuallyLocked, "Cannot add to expired");
    + if (_locked.perpetuallyLocked) {
    +     perpetuallyLockedBalance += _value;
    + }
    //...
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical error in the reward distribution flow of the RewardsDistributor contract. The claim() function decides whether to transfer rewards directly or to call vePeg.deposit_for() based on the lock status. For locks that are marked as perpetual, the contract stores an end timestamp of zero. The deposit_for() implementation checks only that locked.end > block.timestamp and reverts with Cannot add to expired lock. Withdraw when the condition is false. Because zero is never greater than the current timestamp, the check incorrectly treats a perpetual lock as expired, causing the deposit_for() call to revert. As a result, rewards that should be added to a perpetual lock are never deposited, preventing the lock’s voting power from increasing and leaving the user with no visible reward balance. The bug manifests only when a user with a perpetual lock invokes claim() while the lock remains unexpired; normal time‑limited locks work as intended. It was discovered during a manual audit of the claim() logic, where the auditor noticed that the perpetual‑locked branch called deposit_for() without a corresponding exception for the zero‑end case. The issue is subtle because perpetual locks are a legitimate feature and the end field being zero is a valid sentinel value, so a simple expired check appears reasonable at first glance. The impact is high for affected users because they cannot claim rewards, effectively losing potential token accrual and associated voting power, although no funds are stolen. The fix is to modify deposit_for() to accept perpetual locks by adding a condition that allows _locked.perpetuallyLocked or by handling the zero‑end case explicitly, and to update the perpetual‑locked balance accordingly. This change restores the intended accounting where rewards increase the lock’s balance and voting weight, aligning the contract’s behavior with its business logic that perpetual locks should continue to earn rewards.
