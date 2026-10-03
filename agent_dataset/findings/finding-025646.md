---
id: 25646
severity: "Medium"
---

# Locker owners can leverage low liquidity pools to bypass the tax mechanism

## Description



## Proof of Concept

## Impact

Depending on the liquidity present in the pools, a locker owner can bypass the tax mechanism with miniscule amounts lost compared to the normal exits present in the protocol.

## Recommendation

Either make sure there is enough liquidity in the pools or use TWAP oracle to see if the price has been pushed to extreme while withdrawing liquidity.
