---
id: 25709
severity: "Medium"
---

# Swaps should use the deadline argument on top of minimumAmountOut

## Description

Swapping with block.timestamp as deadline means validators may do MEV up to the minimumAmountOut. [https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L441](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L441>) [https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L709](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L709>) [https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L727](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L727>)

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
