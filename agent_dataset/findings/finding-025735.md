---
id: 25735
severity: "Low/Info"
---

# Ownable2Step is preferred over Ownable

## Description

[Ownable2Step](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/access/Ownable2Step.sol>) places some important checks, such as a 2 step ownership transfer procedure and should be preferred over [Ownable](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/access/Ownable.sol>).

## Proof of Concept

No PoC provided.

## Recommendation

Replace Ownable2Step by Ownable whenever possible.
