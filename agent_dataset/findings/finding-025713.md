---
id: 25713
severity: "Low/Info"
---

# Ownable2Step is preferred over Ownable

## Description

Openzeppelin [Ownable2Step](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/access/Ownable2Step.sol>) changes transferOwnership() to a 2 step procedure, which means that to change an owner, first a pending owner is set and only then this account must accept ownership.

This means that it's impossible to set the wrong address as the owner by mistake.

## Proof of Concept

No PoC provided.

## Recommendation

Use Ownable2Step.
