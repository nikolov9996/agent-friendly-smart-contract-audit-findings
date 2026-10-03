---
id: 25065
severity: "Medium"
---

# IDOPoolAbstract does not deal with yield and gas accrued on Blast

## Description

Blast accumulates yield for contracts holding `USDB`, `WETH` and `ETH` and enables contracts to claim some of the gas fees. However, this is not currently dealt with so `IDOPoolAbstract` will miss out on this.

## Proof of Concept

No PoC provided.

## Recommendation

Implement functionality to deal with this yield and gas fees.
