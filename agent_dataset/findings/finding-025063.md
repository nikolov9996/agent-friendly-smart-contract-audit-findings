---
id: 25063
severity: "Low/Info"
---

# Use of address.transfer instead of the recommended address.call{value: amount}("")

## Description

`address.transfer` is unsafe and may lead to stuck tokens as it forwards 2300 gas, which may run out of gas in the fallback function of the receiver. Additionally, future opcode changes could make it stop working.

## Proof of Concept

No PoC provided.

## Recommendation

Use `address.call{value: amount}("")`. Keep in mind that state changes must be performed before sending the funds this way as it opens the door for reentrancy. In `IDOPoolAbstract::claimRefund()`, funds are sent before deleting the position, which would be exploitable.
