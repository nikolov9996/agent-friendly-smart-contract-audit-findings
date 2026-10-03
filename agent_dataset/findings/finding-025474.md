---
id: 25474
severity: "Low/Info"
---

# Structs can be packed to save gas

## Description

In solidity, structs can often be packed into fewer words to save gas on storage loads/stores. In the [code](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/nftperp-types/NFTPStructs.sol>), the following structs can be optimized in this way: LimitOrder, TriggerOrder, TwapInputAsset, MarketOrder.

## Proof of Concept

No PoC provided.

## Recommendation

Reorder the variables in these structs to pack them together.
