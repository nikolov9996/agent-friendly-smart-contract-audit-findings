---
id: 25136
severity: "Low/Info"
---

# D1MemeTokens will be stuck whenever the merkle roots or the free claims are not fully claimed

## Description

In FairLauncher::newFairLaunch(), the total supply of minted D1MemeToken is equal to the presale + lp + freeClaim + airdrop. It's possible some tokens will never be claimed via airdrop or freeClaim, but there is no way to recover them. There is no significant impact as these tokens will just be burned and act as if the real supply is decreased.

## Proof of Concept

No PoC provided.

## Recommendation

The tokens could be reimbursed in some way that is fair but this would increase complexity.
