---
id: 25223
severity: "Low/Info"
---

# avaxAmount is never 0 in withdraw() in the first if (avaxAmount > 0 && ...)

## Description

In function withdraw(), checking [if (avaxAmount > 0)](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L223C1-L223C1>) is not required since it is

```solidity
guaranteed to be true by require(amount > 0, "ZERO_WITHDRAW");
function withdraw(uint256 amount) external nonReentrant {
    ... require(amount > 0, "ZERO_WITHDRAW");
    ... if (avaxAmount > 0 && depositAmount > 0) { // avaxAmount is never 0 ... }
    ...
```

## Proof of Concept

No PoC provided.

## Recommendation

Remove avaxAmount > 0 from the if statement.
