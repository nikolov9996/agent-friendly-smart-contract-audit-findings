---
id: 25460
severity: "Low/Info"
---

# Errors could include relevant arguments whenever possible, making it easier to debug

## Description

While during testing it's possible to get the relevant information using other methods (console.log comes to mind), when the contract is deployed and transactions are live, it's harder to debug without the information being contained in the error.

This could be even more relevant in case of a suspiscious transaction that is being analyzed, where time is very important to prevent damage. See [`ClearingHouse`](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouse.sol#L78-L90>), for example.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
