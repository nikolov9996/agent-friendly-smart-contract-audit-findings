---
id: 25361
severity: "Low/Info"
---

# Usdc to Usds calculation in the Sky Strategy is slightly different than the Psm Usds Wrapper

## Description

In the [psmWrapper](<https://vscode.blockscan.com/ethereum/0xA188EEC8F81263234dA3622A406892F3D630f98c>), the Usds amount from the gem is calculated as usdsInWad = gemAmt18

- gemAmt18 * psm.tout() / WAD; , but in the Sky Strategy it is calculated as (gemAmount_
- to18ConversionFactor * (WAD + tout)) / WAD; .

## Proof of Concept

No PoC provided.

## Recommendation

Although the result is the same (including the rounding error), consider implementing the same exact formula.
