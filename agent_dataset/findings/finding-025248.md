---
id: 25248
severity: "Low/Info"
---

# Unnecessary user balance check in _withdrawRequest()

## Description

The balance of the user when withdrawing against the amount passed in as argument is already checked in the withdraw() function, there's no need to check again in [_withdrawRequest()](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/GlacialAVAX/glAVAX.sol#L632>).

## Proof of Concept

No PoC provided.

## Recommendation

Remove the following line

```solidity
function _withdrawRequest(uint256 amount) internal {
    address user = msg.sender;
    require(amount <= balanceOf(user), "INSUFFICIENT_BALANCE"); // remove
this line
... }
```
