---
id: 25387
severity: "Crit/High"
---

# Lost nfts due to smart wallets having different addresses on different chains

## Description

[send()](<https://github.com/threesigmaxyz/metazero-issues-external/blob/master/src/ONFTV2-721C.sol#L98>) sends the tokens to the same address that called the function. Some smart contract wallets may have different addresses on different chains (or even chains with different address generation).

## Proof of Concept

No PoC provided.

## Recommendation

Let the user specify a destination address to send the nfts to.
