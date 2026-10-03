---
id: 25099
severity: "Low/Info"
---

# Rebalancing back to original lower and upper ticks will not deposit nft to farm

## Description

Rebalance changes the lower and upper ticks in PHyperLPoolSwapInside and withdraw from the farming contract if it is allocated. If the rebalance is performed to a previously used lower and upper ticks, the nftId will not be 0 and it will [add](<https://github.com/ClipFinance/StrategyRouter-private/pull/107/files#diff-023946f07f510e865612a28a9a222e00f0f6b90a253fd981e9bf4f7656f5497fR364>) liquidity instead of minting.

As can be seen, the add liquidity branch does not deposit to the farming contract if it is not allocated yet.

## Proof of Concept

No PoC provided.

## Recommendation

The impact is reduced as it can be deposited later by calling [PHyperLPoolSwapInside::depositNftToFarm()](<https://github.com/ClipFinance/StrategyRouter-private/pull/107/files#diff-023946f07f510e865612a28a9a222e00f0f6b90a253fd981e9bf4f7656f5497fR122>).

Consider try allocating after the _mint() call if it is not allocated yet (and setting the allocatedToFarming bool to true)
