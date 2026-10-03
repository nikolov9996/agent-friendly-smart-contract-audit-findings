---
id: 25706
severity: "Medium"
---

# address(0) can be added as a pair, triggering taxes on burn

## Description

A pair with zero address may be [added](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L246>) to the pairs mapping which means burns will be taxed.

## Proof of Concept

No PoC provided.

## Recommendation

Revert if the pair does not exist in recordAmmPairWith().
