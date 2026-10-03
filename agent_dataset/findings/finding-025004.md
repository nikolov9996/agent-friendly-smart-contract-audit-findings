---
id: 25004
severity: "Low/Info"
---

# Donation attack possible, although unlikely, could make an initial deposit

## Description



## Proof of Concept

## Vulnerability Detail

Essentially the attack is as follows:

1. Attacker mints 1 shares.
2. Attacker donates `YUSD` to `sYUSD`.
3. User deposits and mints 0 or a rounded down amount of shares (specifying that shares minted > 0 is not enough because if it rounds down to 1, 2 or similar the user also takes losses).

This is mitigated by the current ERC4626 implementation as it results in:

1. Attacker mints 1 shares.
2. Attacker donates 10e18 assets + 1.
3. If the attacker redeems their share, they get `1 * (1e18 + 1 + 1) / (1 + 1) = 0.5e18`.

However, a user may still get caught in this: Step 4, user deposits 4e18 assets, getting `4e18 * (1 + 1) / (10e18 + 1) = 0` shares.

## Impact

Attacker steals user funds

## Code Snippet

[https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC4626.sol#L225-L227](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC4626.sol#L225-L227>)

## Recommendation

Make an initial, small deposit and keep it deposited to fully prevent these attacks.
