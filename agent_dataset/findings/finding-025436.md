---
id: 25436
severity: "Medium"
---

# LoopStrategy is vulnerable to inflation attacks

## Description

LoopStrategy inherits ERC4626Upgradeable, which calculates shares deposited as

```solidity
(_decimalsOffset() is 0): shares = assets * (totalSupply() + 1) / (totalAssets() + 1);
```

As such, the following attack is possible:

- User deposits 1e18 assets.
- Attacker frontruns and deposits 1 asset, minting 1 * 1 / 1 = 1 share.
- Attacker donates 2e18 worth of vault shares to the market.
- User1 deposits 1e18 assets and receives no shares, shares = 1e18 * 2 / (2e18 + 1) = 0.
- User2 deposits 1.5e18 assets and receives no shares, shares = 1.5e18 * 2 / (3e18 +

1. = 0.

- Attacker redeems 1 * (4.5e18 + 1) / (1+1) = 2.25e18.

## Proof of Concept

No PoC provided.

## Recommendation

Consider using a bigger decimals offset or do an initial deposit.
