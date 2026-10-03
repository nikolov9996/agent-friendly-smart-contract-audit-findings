---
id: 25712
severity: "Low/Info"
---

# Native transfers should use Openzeppelin's .sendValue()

## Description

Paying fees to the marketing operator uses [.transfer()](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L291>), which only forwards 2300 gas, which could lead to reverts if the operator has any logic in the fallback or receive functions.

## Proof of Concept

No PoC provided.

## Recommendation

Use [.sendValue()](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/Address.sol#L41>) from Openzeppelin's Address.sol.
