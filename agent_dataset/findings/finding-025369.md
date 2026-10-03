---
id: 25369
severity: "Low/Info"
---

# Attacker may frontrun SyrupRouter::depositWithPermit() call and use a different depositData_ as it is not signed

## Description

[SyrupRouter::depositWithPermit()](<https://github.com/maple-labs/syrup-router/blob/main/contracts/SyrupRouter.sol#L39>) accepts a permit signature and a depositData_ as extra data to be emitted. An attacker may spot the signature and frontrun the transaction, but with a differerent depositData_, griefing the user.

## Proof of Concept

No PoC provided.

## Recommendation

A simple fix is not possible as the permit function does not accept any extra data. It should be possible to send the transaction through flashbots to mitigate this issue if needed.
