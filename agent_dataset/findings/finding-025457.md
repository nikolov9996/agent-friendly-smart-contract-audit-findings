---
id: 25457
severity: "Low/Info"
---

# Contracts should inherit their interfaces

## Description

To avoid differences between the function declarations in the contracts and their interfaces, it is a good practice for contracts to inherit their interfaces.

At the moment the [AMM](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol>) contract doesn't inherit the [IAMM](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/interfaces/IAMM.sol>) interface and this leads to problems of functions existing in the interface but not the contract.

For instance, functions getInitializationPrice(), getLiquidationParams() and getReservesAndTotalLiquidity(). In the future a user might try to interact with the protocol using the interface, but the call would certainly revert due to this issue.

## Proof of Concept

No PoC provided.

## Recommendation

No recommendation provided.
