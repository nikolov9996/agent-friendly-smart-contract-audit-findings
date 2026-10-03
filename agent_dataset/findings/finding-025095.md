---
id: 25095
severity: "Low/Info"
---

# PHyperLPoolSwapInside::_swapWithCustomData() should check if the router has code

## Description

[PHyperLPoolSwapInside::_swapWithCustomData()](<https://github.com/ClipFinance/StrategyRouter-private/pull/107/files#diff-023946f07f510e865612a28a9a222e00f0f6b90a253fd981e9bf4f7656f5497fR588>) performs swap using a router provided as argument in swapData.

Solidity performs contract length checks when using an interface, but not when using .call(), making this call dangerous as success will be true.

## Proof of Concept

No PoC provided.

## Recommendation

Use Openzeppelin's [Address::functionCall()](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/Address.sol#L62>) which performs all the checks.
