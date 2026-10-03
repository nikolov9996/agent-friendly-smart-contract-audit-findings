---
id: 25710
severity: "Medium"
---

# createAmmPairWith() in initialize() will revert if the pair already exists

## Description

[createAmmPairWith()](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L435>) in initialize() reverts if the pair exists, which means that the contract could be DoSed.

## Proof of Concept

No PoC provided.

## Recommendation

Check if the pair already exists and skip creating if it does. However, this would make [addLiquidityETH()](<https://github.com/TrestleProtocol/Audit-Contracts/blob/main/src/Trestle.sol#L441>) vulnerable to slippage, so introduce slippage control arguments.
