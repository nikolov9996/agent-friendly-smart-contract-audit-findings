---
id: 25110
severity: "Medium"
---

# Admin will not be able to only pause deposits in the Vault due to incorrect check leading to DoSed withdrawals

## Description



## Proof of Concept

`ModuleState::LVDepositNotPaused()` is incorrect:

```solidity
modifier LVDepositNotPaused(Id id) {
    if (states[id].vault.config.isWithdrawalPaused) { //@audit isDepositPaused
        revert LVDepositPaused();
    }
    _;
}
```

## Recommendation

`ModuleState::LVDepositNotPaused()` should be:

```solidity
modifier LVDepositNotPaused(Id id) {
    if (states[id].vault.config.isDepositPaused) {
        revert LVDepositPaused();
    }
    _;
}
```
