---
id: 25459
severity: "Medium"
---

# setFundingPeriod() can be DoSed due to calling settleFunding()

## Description

[setFundingPeriod()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/AMM.sol#L856>) calls [settleFunding()](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/1c16f2010a851ac23aec73822d55388901bbe5e7/src/ClearingHouse.sol#L523>) in the ClearingHouse.

It may be the case that someone frontruns setFundingPeriod() with a call to settleFunding(), making the setFundingPeriod() transaction revert.

## Proof of Concept

No PoC provided.

## Recommendation

Make the funding payments pro-rata to time instead of in fixed intervals. This would also solve the fact that settleFunding() calls can be frontrunned to avoid payments.
