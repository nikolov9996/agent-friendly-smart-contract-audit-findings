---
id: 25360
severity: "Low/Info"
---

# MapleSkyStrategy:: _gemForUsds() suffers a rounding error up to approximately 1e12 Usds

## Description

MapleSkyStrategy:: _gemForUsds() computes gemAmount_ = (usdsAmount_ * WAD) / (to18ConversionFactor * (WAD + tout));. As can be seen, to18ConversionFactor is 1e12 for a Usdc gem, which leads to a rounding up to 1e12 Usds.

## Proof of Concept

No PoC provided.

## Recommendation

As the rounding [error](<https://github.com/aave-dao/aave-v3-origin/blob/main/src/contracts/protocol/libraries/helpers/Errors.sol#L40>) corresponds to only 1e-6 USD and the operation is not called frequently, it's safe to ignore it.
