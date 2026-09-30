---
id: 8713
severity: "Critical"
---

# NAV Value Overwrites Last Fee Harvest Time

## Description

The VaultStore library defines a critical storage key incorrectly:  
```solidity
bytes32 public constant LAST_HARVEST_PERFORMANCE_FEE_TIME = keccak256(abi.encode("NAV"));
```  
Instead of using a unique identifier for the last performance fee harvest time, it reuses the same key as NAV.  
When setVaultState() is called (e.g., in _updateVaultState()), it stores the NAV value in LAST_HARVEST_PERFORMANCE_FEE_TIME. Consequently, getLastHarvestPerformanceFeeTime() returns the NAV value instead of the expected timestamp.  
This causes harvestPerformanceFee() to always revert because:

```solidity
require(block.timestamp >= lastHarvest + minHarvestInterval, "HARVEST_TOO_SOON");
```

Since lastHarvest is set to a large NAV value, the condition will never pass.

Performance fees cannot be collected, leading to lost protocol revenue.

## Proof of Concept

no poc

## Recommendation

Fix the storage key to use the correct identifier:  
```solidity
bytes32 public constant LAST_HARVEST_PERFORMANCE_FEE_TIME = keccak256(abi.encode("LAST_HARVEST_PERFORMANCE_FEE_TIME"));
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a storage‑key collision that causes the Net Asset Value (NAV) of a vault to overwrite the timestamp that records the last performance‑fee harvest. In the VaultStore library a constant is defined as LAST_HARVEST_PERFORMANCE_FEE_TIME = keccak256(abi.encode('NAV')). Because the same hash is used for the NAV variable elsewhere, when setVaultState (called during _updateVaultState) writes the current NAV into storage, it unintentionally stores that large numeric value in the slot reserved for the last harvest time. Consequently, the getter getLastHarvestPerformanceFeeTime returns the NAV value instead of a Unix timestamp. The harvestPerformanceFee function checks require(block.timestamp >= lastHarvest + minHarvestInterval, 'HARVEST_TOO_SOON');. Since lastHarvest now holds a huge NAV number, the condition can never be satisfied and the function always reverts. The impact is that performance fees, which should be collected after a configurable interval, are never harvested, resulting in lost protocol revenue. Users do not see a direct loss of their deposited assets, but the protocol’s economic model is broken because expected fee income never materialises. The bug manifests whenever the vault state is updated – essentially on every deposit, withdrawal, or profit‑realisation event – because setVaultState is invoked each time. It was discovered during a manual audit that inspected storage constants and noticed that the identifier for the last harvest time was incorrectly set to the string "NAV". The issue is subtle because the revert message "HARVEST_TOO_SOON" appears normal and does not hint at a corrupted timestamp, making it easy to overlook during functional testing. The class of bug is a mis‑named or colliding storage key, a form of state‑variable aliasing that leads to incorrect data being written to a critical accounting field. To remediate, the constant should be defined with a unique identifier, for example LAST_HARVEST_PERFORMANCE_FEE_TIME = keccak256(abi.encode('LAST_HARVEST_PERFORMANCE_FEE_TIME')), ensuring that the NAV and the harvest timestamp occupy distinct storage slots. This change restores the correct accounting of fee harvest times and allows the performance‑fee mechanism to operate as intended, preserving expected revenue streams.
