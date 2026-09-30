---
id: 20260
severity: "High"
---

# Vault.sol: settling the 0 address will disrupt global accounting

## Description

Within Vault#_loadContext function, the context.global is the account of the 0 address, while context.local is the account of the address to be updated or settled:
```solidity
function _loadContext(address account) private view returns (Context memory context) {
    ...
    context.global = _accounts[address(0)].read();
    context.local = _accounts[account].read();
    context.latestCheckpoint = _checkpoints[context.global.latest].read();
}
```
If a user settles the 0 address, the global account will be updated with wrong data. Here is the _settle logic:
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
            context.latestCheckpoint.deposit,
            context.latestCheckpoint.redemption
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
If settle is called on 0 address, _loadContext will give context.global and context.local same data. In the _settle logic, after the global account(0 address) is updated with the correct data in the while loop(specifically through the processGlobal function), the global account gets reupdated with wrong data within the if statement through the processLocal function. Wrong assets and shares will be recorded. The global account's assets and shares should be calculated with toAssetsGlobal and toSharesGlobal respectively, but now, they are calculated with toAssetsLocal and toSharesLocal. toAssetsGlobal subtracts the globalKeeperFees from the global deposited assets, while toAssetsLocal subtracts globalKeeperFees/Checkpoint.count fees from the local account's assets. So in the case of settling the 0 address, where global account and local account are both 0 address, within the while loop of _settle function, depositedAssets-globalKeeperFees is recorded for address(0), but then, in the if statement, depositedAssets-(globalAssets/Checkpoint.count) is recorded for address(0). And within the Vault#_saveContext function, context.global is saved before context.local, so in this case, context.global(which is 0 address with correct data) is overridden with context.local(which is 0 address with wrong data). The global account will be updated with wrong data, that is, global assets and shares will be higher than it should be because lower keeper fees was deducted.

## Proof of Concept

no poc

## Recommendation

I believe that the ability to settle the 0 address is intended, so an easy fix is to save local context before saving global context: Before:
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

The vulnerability resides in the Vault contract’s accounting routine that separates a global accounting record (stored at the zero address) from a per‑account local record. The private function _loadContext reads the global state from _accounts[address(0)] and the local state from _accounts[account]. When the settle function is called with the zero address as the target, both context.global and context.local point to the same storage slot. The subsequent _settle routine first updates the global record inside a while‑loop by calling processGlobal, which correctly applies the global keeper fee using the toAssetsGlobal / toSharesGlobal formulas. Immediately after, the if‑branch treats the same storage as a local record and calls processLocal, which uses the toAssetsLocal / toSharesLocal formulas that deduct a different (typically smaller) fee amount. Because the same account is written twice, the second write overwrites the correct global values with the locally calculated ones, inflating the recorded assets and shares for the global account. The bug is compounded by _saveContext, which stores the global context first and then the local context; when both contexts refer to the zero address, the later store of the local context overwrites the previously saved correct global data. The result is a global accounting state that shows more assets and shares than actually exist, breaking the protocol’s invariant that total global assets equal the sum of all deposits minus fees. This can be exploited by any caller who can trigger a settlement on the zero address, causing the protocol to believe it holds extra collateral and potentially allowing unauthorized withdrawals or causing liquidation logic to behave incorrectly. The issue appears only when the zero address is used as the settlement target, a path that is rarely exercised in normal operation, which makes the bug hard to notice during functional testing. The vulnerability was identified during a manual audit of the contract’s accounting flow. To remediate, the contract should either forbid settling the zero address or ensure that the global and local contexts are saved in a non‑overlapping order (for example, persisting the local context before the global one) so that a later write does not corrupt the global record. Conceptually, the fix separates the two accounting domains or protects the sentinel address from being treated as a regular account.
