---
id: 25738
severity: "Low/Info"
---

# Precision loss due to engines not using .muldiv() when calculating lp ratios

## Description

For example, in SpotEngineState::_getInLpBalance(), the [ratio](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/SpotEngineState.sol#L338>) is calculated first, likely incurring in precision loss as lpState.supply is expected to be bigger than 1e18 (used in .div()).

This means that baseAmount and quoteAmount will be smaller due to the precision loss.

## Proof of Concept

No PoC provided.

## Recommendation

Everytime a division and multiplication are to be applied and division loss could occur (when the denominator is bigger than 1e18), [mulDiv()](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/math/Math.sol#L128>) should be used. [https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/SpotEngineLP.sol#L38](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/SpotEngineLP.sol#L38>) [https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngineState.sol#L115](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngineState.sol#L115>) [https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngine.sol#L174](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngine.sol#L174>) [https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngine.sol#L177](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngine.sol#L177>)
