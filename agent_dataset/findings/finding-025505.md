---
id: 25505
severity: "Low/Info"
---

# Reentrancy guard can be implemented with a uint256 to save gas

## Description

Storing a uint256 instead of a bool saves gas as it is cheaper changing storage from non null to non null value.

## Proof of Concept

No PoC provided.

## Recommendation

Implement the guard with a uint256. [Here](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/ReentrancyGuard.sol#L37-L38>) is an example implementation from OpenZeppelin.
