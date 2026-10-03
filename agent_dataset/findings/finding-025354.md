---
id: 25354
severity: "Low/Info"
---

# There may not be enough gem(Usdc) in the Psm contract, DoSing withdrawals in the Sky Strategy

## Description

The [psm](<https://vscode.blockscan.com/ethereum/0xf6e72Db5454dd049d0788e411b06CfAF16853042>) contract may not have enough gem (USDC) in the pocket, which could revert and DoS withdrawals.

## Proof of Concept

No PoC provided.

## Recommendation

It's possible to change the psm address so the issue can be managed, but it could DoS withdrawals for some time.
