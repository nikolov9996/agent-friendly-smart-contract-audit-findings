---
id: 25237
severity: "Low/Info"
---

# Remove unused imports

## Description

If an import is never used it should be removed to save on code size. In wglAVAX imports PausableUpgradeable, IWAVAX, IGReservePool, IGLendingPool, AcessControlManager and GlacierAddressBook are never used. In GLendingPool import console is not used.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
