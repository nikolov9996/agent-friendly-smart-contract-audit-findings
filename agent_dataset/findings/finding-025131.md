---
id: 25131
severity: "Medium"
---

# FairLauncher inherits BlastNoYieldAdapter but will hold ETH

## Description

Blast earns yield for addresses that hold ETH. The FairLauncher contract will hold ETH due to the sales, but inherits BlastNoYieldAdapter, which does not configure the Blast address yield to claimable.

## Proof of Concept

No PoC provided.

## Recommendation

Inherit BlastAdapter instead of BlastNoYieldAdapter to claimed the yield from ETH.
