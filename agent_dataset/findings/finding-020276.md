---
id: 20276
severity: "High"
---

# Vault.sol: settling the 0 address will disrupt

## Description

Within Vault#_loadContext function, the context.global is the account of the 0
address, while context.local is the account of the address to be updated or settled:
```solidity
function _loadContext(address account) private view returns (Context memory
context) {
    ...
    context.global = _accounts[address(0)].read();
    context.local = _accounts[account].read();
    context.latestCheckpoint = _checkpoints[context.global.latest].read();
}
```
If a user settles the 0 address, the global account will be updated with wrong data.
Here is the _settle logic:
```solidity
function _settle(Context memory context) private {
    // settle global positions
    while (
        context.global.current > context.global.latest &&
        _mappings[context.global.latest + 1].read().ready(context.latestIds)
    ) {
        uint256 newLatestId = context.global.latest + 1;
        context.latestCheckpoint = _checkpoints[newLatestId].read();
        _collateralAtId(context, newLatestId);
        context.latestCheckpoint.complete(collateralAtId, feeAtId, keeperAtId);
        context.global.processGlobal(
            newLatestId,
            context.latestCheckpoint,
            context.global.deposit,
            context.global.redemption
        );
        _checkpoints[newLatestId].store(context.latestCheckpoint);
    }
    // settle local position
    if (
        context.local.current > context.local.latest &&
        _mappings[context.local.current].read().ready(context.latestIds)
    ) {
        uint256 newLatestId = context.local.current;
        Checkpoint memory checkpoint = _checkpoints[newLatestId].read();
        context.local.processLocal(
            newLatestId,
            checkpoint,
            context.local.deposit,
            context.local.redemption
        );
    }
}
```
If settle is called on 0 address, _loadContext will give context.global and
context.local same data. In the _settle logic, after the global account(0 address) is
updated with the correct data in the while loop(specifically through the
processGlobal function), the global account gets reupdated with wrong data within
the if statement through the processLocal function.
Wrong assets and shares will be recorded. The global account's assets and shares
should be calculated with toAssetsGlobal and toSharesGlobal respectively, but
now, they are calculated with toAssetsLocal and toSharesLocal.
toAssetsGlobal subtracts the globalKeeperFees from the global deposited assets,
while toAssetsLocal subtracts globalKeeperFees/Checkpoint.count fees from the
local account's assets.
So in the case of settling the 0 address, where global account and local account
are both 0 address, within the while loop of _settle function,
depositedAssets-globalKeeperFees is recorded for address(0), but then, in the if
statement, depositedAssets-(globalAssets/Checkpoint.count) is recorded for
address(0).
And within the Vault#_saveContext function, context.global is saved before
context.local, so in this case, context.global(which is 0 address with correct data)
is overridden with context.local(which is 0 address with wrong data).
The global account will be updated with wrong data, that is, global assets and
shares will be higher than it should be because lower keeper fees was deducted.

## Proof of Concept

no poc

## Recommendation

I believe that the ability to settle the 0 address is intended, so an easy fix is to save
local context before saving global context: Before:
```solidity
function _saveContext(Context memory context, address account) private {
    _accounts[address(0)].store(context.global);
    _accounts[account].store(context.local);
    _checkpoints[context.currentId].store(context.currentCheckpoint);
}
```
After:
```solidity
function _saveContext(Context memory context, address account) private {
    _accounts[account].store(context.local);
    _accounts[address(0)].store(context.global);
    _checkpoints[context.currentId].store(context.currentCheckpoint);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the vault contract’s settlement routine when the zero address (address(0)) is used as the target of a settle operation. The function that loads the accounting context, _loadContext, reads the global accounting record from the storage slot reserved for address(0) and also reads the local record from the address supplied by the caller. When the caller passes address(0), both context.global and context.local point to the same storage entry, meaning the contract treats the global state and the user‑specific state as identical. During settlement, the _settle function first processes global positions in a while‑loop that updates the global account using the correct global fee calculation (toAssetsGlobal / toSharesGlobal). Immediately afterwards, the same function processes the local position in an if‑statement that calls processLocal, which applies the local fee formula (toAssetsLocal / toSharesLocal). Because context.global and context.local reference the same storage entry, the second step overwrites the previously correct global values with those computed using the local formula, which deducts a different amount of keeper fees. The bug is compounded by the _saveContext routine, which stores the global context first and then the local context; when both refer to address(0), the later write of the local context overwrites the correct global data with the incorrect values. As a result, the global accounting record for the vault can end up with inflated assets and shares, because the fee subtraction is smaller than it should be. This mis‑recording can be triggered by any user who is able to call settle on address(0), leading to a situation where the protocol’s total balance appears larger than the actual deposited funds, potentially allowing malicious actors to withdraw more than they are entitled to or causing honest users to receive incorrect payouts. The issue was discovered during a manual audit that examined the flow of data between the global and local accounting structures. It is difficult to notice because the zero address is rarely used in normal operation, and the symptom – a gradual drift in the global totals – does not produce an outright failure or revert, making the discrepancy easy to miss in routine testing. The proper remediation is to prevent the zero address from being settled, or to ensure that the global and local contexts are saved in the correct order (saving the local context before the global one) so that a later write does not overwrite the correct global state. Conceptually, the fix separates the handling of the protocol‑wide accounting record from any per‑account updates, thereby preserving the integrity of the global fee calculations and preventing inflated balances.
