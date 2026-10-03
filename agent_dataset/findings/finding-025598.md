---
id: 25598
severity: "Low/Info"
---

# Decimals in ZKToken are not set to the underlying decimals, which will likely harm tvl calculations in aggregators

## Description

ZKTokens are minted 1:1 to the underlying assets, so should inherit the same decimals. For example, if USDT is the underlying asset, and 100 USDT are locked, it will mint 100e6 ZKTokens. As the decimals are 1e18 in the OpenZeppelin implementation, this will equal much less TVL.

## Proof of Concept

No PoC provided.

## Recommendation

Change the constructor to set the decimals according to the underlying asset. Keep in mind that decimals are not part of the standard, so it may be required to manually set the decimals to the right value.
