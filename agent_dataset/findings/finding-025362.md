---
id: 25362
severity: "Low/Info"
---

# Withdrawals in the Maple Pool and Sky Strategy may be DoSed in case the DssLitePsm halts buying

## Description

The [DssLitePsm](<https://vscode.blockscan.com/ethereum/0xf6e72Db5454dd049d0788e411b06CfAF16853042>), used as part of the Usds Psm wrapper that allows converting fundsAsset to Usds in the Sky Strategy, may be halted by setting tout to type(uint256).max.

In this case, MapleSkyStrategy::assetsUnderManagement() would revert due to overflow when calculating the underlying balance of the strategy.

As such, withdrawals would be DoSed in the Maple Pool.

## Proof of Concept

No PoC provided.

## Recommendation

The issue can be resolved by setting the pool to inactive, although other solutions are possible. In this case, halting withdrawals may actually be the desired outcome, but it's something to keep in mind.
