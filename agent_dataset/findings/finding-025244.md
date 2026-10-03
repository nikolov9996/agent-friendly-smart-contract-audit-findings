---
id: 25244
severity: "Low/Info"
---

# Storage variables should be cached whenever possible to save gas

## Description

Storage reads should be avoided whenever possible to save gas, which can be achieved by caching the variables in memory.

## Proof of Concept

No PoC provided.

## Recommendation

For example, in [_withdrawRequest()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L632>), the variables totalWithdrawRequests and userWithdrawRequestCount can be cached.
