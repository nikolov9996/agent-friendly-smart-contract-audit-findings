---
id: 25715
severity: "Low/Info"
---

# totalShares update should add before reducing to avoid underflows

## Description

totalShares [update](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L685>) subtracts before summing, which could lead to underflow in edge cases (when something unexpected happens).

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
