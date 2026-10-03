---
id: 25246
severity: "Low/Info"
---

# Implement _transferShares() to prevent having to convert shares/wAVAX twice in glAVAX

## Description

Sometimes the quantity of shares on hand is available instead of the corresponding wAVAX amount. In this case, if shares are to be transferred internally, it's easier to use _transferShares() instead of having the shares, converting to amount and calling [_transfer()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L701-L708>), which converts back to shares.

## Proof of Concept

No PoC provided.

## Recommendation

For example, in cancel(), the shares are available from request.shares, are converted to wAVAX amount and then back to shares again in _transfer().
