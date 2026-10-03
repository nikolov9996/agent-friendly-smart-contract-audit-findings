---
id: 25456
severity: "Low/Info"
---

# removeLiquidity() in the amm calculates marginToRemove without updating the margin with the funding payment

## Description

[removeLiquidity()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol#L645>) removes the margin from the position pro-rata to the removed shares, without considering the previous funding payment.

The impact should be limited to the case when a significant amount of shares is removed and the fundingPayment is applied after the margin removal, which may lead to bad debt and [revert](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol#L647>).

## Proof of Concept

No PoC provided.

## Recommendation

Add the fundingPayment to the margin and only then calculate marginToRemove.
