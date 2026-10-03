---
id: 25739
severity: "Low/Info"
---

# Ratios in PerpEngineLp or SpotEngineLp may be manipulated when the liquidity is low

## Description

[PerpEngineLp::mintLp()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngineLp.sol#L36-L38>) assigns quote according to

```solidity
int128 amountQuote = (lpState.base == 0) ? amountBase.mul(_risk(productId).priceX18) : amountBase.mul(lpState.quote.div(lpState.base));
```

with the requirement that amountBase % sizeIncrement == 0. In [PerpEngineLp::burnLp()](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/PerpEngineLp.sol#L91-L98>), the amounts received are amountBase = MathHelper.floor( int128((int256(amountLp) * lpState.base) / lpState.supply), sizeIncrement ); amountQuote = int128( (int256(amountLp) * lpState.quote) / lpState.supply ); Thus, with low enough liquidity, the price of the perp engine may be lowered close to 0 by exploiting Math.floor() or similar strategies and increased up to 1/sizeIncrement.

See the [poc](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/foundry-set-up/test/TestManipulatePerpLpRatios.t.sol>) for details. The same can be said for the spot engine, with the upper limit of the price being 1.

Note: due to how the health calculation works, changing the prices always leads to less health factor and pnl so it's likely this can not be used to exploit for profit, but users may still be griefed.

## Proof of Concept

No PoC provided.

## Recommendation

Do an initial lp provision to prevent price manipulations.
