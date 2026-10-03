---
id: 25483
severity: "Medium"
---

# It's possible to mint an infinite number of shares without increasing quote or base amounts, due to rounding down

## Description

For very low notional amounts, when adding liquidity, [invariantIncrease](<https://github.com/nftperp/NFTPerp-V2-Contracts/blob/8ea05fc0ecf299ca8374b571486846652c8725f8/src/AMM.sol#L594>) is always bigger than 0 (not true for the first depositer though), but the corresponding quote and base amounts might be 0.

This means that malicious users could loop addLiquidity() calls, minting a very low amount of shares each time, without ever increasing quote and base. It is most likely not profitable to perform this shares inflation, but some way could be found to exploit it in a way that is profitable.

Plugging in some numbers, it was found that it is possible to mint 22 shares with 0 quote and base amount, which if looped enough times could change the pool state significantly.

## Proof of Concept

No PoC provided.

## Recommendation

Add a minimum notional amount when adding liquidity to reduce the attack surface.
