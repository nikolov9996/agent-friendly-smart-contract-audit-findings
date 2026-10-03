---
id: 25135
severity: "Medium"
---

# Any signature is valid before the issuer address is set

## Description

The issuerAddress in the FairLauncher and TokenVault is not set in the constructor and the signature libraries do not check if ecrecover returns address(0).

Thus, before the issuerAddress is set, it is possible to forge signatures. This could be problematic for example in the TokenVault as there is no on chain balance tracking, so users may withdraw all the balance.

However, this is not very likely because honest users will not deposit in the TokenVault if the issuerAddress has not been set.

## Proof of Concept

No PoC provided.

## Recommendation

Either set the issuerAddress in the constructor or revert if ecrecover() returns address(0).
