---
id: 25242
severity: "Low/Info"
---

# rebalance() in glAVAX reverts if currentReserves == reserveTarget

## Description

[rebalance()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L314>) in glAVAX deposits to the ReservePool if there is available liquidity (balance) and the currentReserves are smaller than the reserveTarget.

The problem is that the ReservePool reverts when trying to [withdraw 0](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/ReservePool/GReservePool.sol#L192>), which is the case if currentReserves == reserveTarget.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
