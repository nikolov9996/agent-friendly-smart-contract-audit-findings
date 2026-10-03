---
id: 25224
severity: "Low/Info"
---

# In glAVAX, should use .call instead of .transfer

## Description

The functions [withdraw()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L252>) and [_claim()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L687>) make transfers directly to the user using payable(user).transfer(amount). .transfer can only forward 2300 gas which means it can fail for some contracts and stop withdraws. .call should be used instead, for example user.call{value: amount}("").

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
