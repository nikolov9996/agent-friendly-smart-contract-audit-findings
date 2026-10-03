---
id: 25236
severity: "Low/Info"
---

# receive() in glAVAX should only allow wAVAX

## Description

The current implementation of the [receive()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L158>) function in glAVAX allows any smart contract to call it, leading to lost funds.

```solidity
receive() external payable {
    // prevents direct sending from a user
    require(msg.sender != tx.origin);
}
```

## Proof of Concept

No PoC provided.

## Recommendation

Refactor the function to only allow transfers from wAVAX.

```solidity
receive() external payable {
    require(msg.sender == addresses.wavaxAddress());
}
```
