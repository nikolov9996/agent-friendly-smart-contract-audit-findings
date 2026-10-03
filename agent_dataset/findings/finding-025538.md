---
id: 25538
severity: "Low/Info"
---

# Ownable2Step is recommended over Ownable

## Description

Ownable uses a dangerous pattern of setting the address without proper checks. This means that if a mistake is made and ownership is transferred to the wrong address, the owner functionalities would be forever lost.

## Proof of Concept

No PoC provided.

## Recommendation

[Ownable2Step](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/access/Ownable2Step.sol>) eliminates this risk by using a 2 step pattern by setting a pending governor and having it accept ownership.
