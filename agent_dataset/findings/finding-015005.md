---
id: 15005
severity: "High"
---

# The Variable maxscale Is Not Saved

## Description

Situation:
In the function _collect() of Divider.sol, the value maxscale is updated in a temporary variable. However, this temporary variable is not written back to its origin. This means the value of maxscale is not kept over time.
```solidity
function _collect(...) internal returns (uint256 collected) {
    ...
    Series memory _series = series[adapter][maturity];
    ...
    // If this is larger than the largest scale we've seen for this Series, use it
    if (cscale > _series.maxscale) {
        // _series is a local variable
        _series.maxscale = cscale;
        lscales[adapter][maturity][usr] = cscale;
    // If not, use the previously noted max scale value
    } else {
        lscales[adapter][maturity][usr] = _series.maxscale;
    }
} // _series is not saved to series[adapter][maturity]
```

## Proof of Concept

no poc

## Recommendation

Do one of the following:
• Replace memory with storage. This way any access to _series translates to sload/sstore.
```solidity
Series storage _series = series[adapter][maturity];
```
• At the end of function _collect(), add the following to "save" the value of _series.maxscale. This is assuming maxscale is the only part that has to be saved.
```solidity
series[adapter][maturity].maxscale = _series.maxscale;
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a state‑persistence bug in the internal _collect function of the Divider contract. The function reads a Series struct from storage into a local memory variable called _series, updates the maxscale field of that memory copy, and then uses the updated value to write a per‑user scale entry (lscales). However, because _series resides in memory, the modified maxscale is never written back to the persistent storage slot series[adapter][maturity]. As a result, the contract does not remember the highest scale that has ever been observed for a given series. The root cause is the misuse of a memory reference where a storage reference is required, combined with the omission of an explicit write‑back for the updated field. An attacker or any user can exploit this by triggering a collection with a larger cscale value; the contract will temporarily record the larger maxscale for that transaction, but the value will be lost after the function returns. Subsequent collections will therefore operate with an outdated maxscale, causing the scaling calculation to be performed with a lower factor than intended. This mis‑calculation can lead to users receiving less than their entitled amount, or conversely, the protocol may credit more than it should, breaking the accounting invariants of the system. The impact is high because the bug affects the core accounting logic of the protocol, potentially resulting in systematic under‑payment of users, loss of trust, and financial loss if the protocol’s token economics rely on accurate scaling. The condition under which the bug manifests is any call to _collect where the current scale (cscale) exceeds the previously stored maxscale; the temporary update is applied but never persisted. All participants that rely on correct scaling – token holders, liquidity providers, and the protocol itself – are affected. The issue was discovered during a manual security audit that examined storage handling patterns and identified that the Series struct was declared as memory instead of storage, and that no explicit assignment back to the storage mapping was performed. The bug is subtle because the function appears to update maxscale correctly, and the per‑user mapping receives the new value, giving the impression that the state is consistent, while the global maxscale remains stale. To fix the issue, the Series variable should be declared as a storage pointer so that any field modifications are automatically persisted, or an explicit assignment such as series[adapter][maturity].maxscale = _series.maxscale should be added at the end of the function to ensure the updated maxscale is saved. This correction restores the intended invariant that the contract always tracks the highest observed scale, preventing accounting errors and protecting user funds.
