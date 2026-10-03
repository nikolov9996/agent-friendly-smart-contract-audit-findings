---
id: 25535
severity: "Low/Info"
---

# OstiumVault::lockDiscount() may revert due to division by 0

## Description

[OstiumVault::lockDiscount()](<https://github.com/0xOstium/smart-contracts-threeSigma/blob/audit-feedback/src/OstiumVault.sol#L83>) reverts if maxDiscountThresholdP == uint16(100) * PRECISION_2, but the constructor and updateMaxDiscountThresholdP() allow setting it to this value.

## Proof of Concept

No PoC provided.

## Recommendation

Also check for equality by using <= instead of <.
