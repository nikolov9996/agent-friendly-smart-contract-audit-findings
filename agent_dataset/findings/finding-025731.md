---
id: 25731
severity: "Crit/High"
---

# ClearingHouseLiq::_assertLiquidationAmount() may increase basis points due to negative quoteBalance.amount + insurance

## Description

If the position is a spread, it may be liquidated as one up to the minimum absolute value of the spot and perp positions. If the spot is short, the liquidatee + insurace need to have enough quote to buy back the spot position.

This [check](<https://github.com/vertex-protocol/vertex-contracts-3sigma-audit/blob/main/contracts/ClearinghouseLiq.sol#L188-L193>) is performed in

```solidity
ClearingHouseLiq::_assertLiquidationAmount(): ...
```

basisAmount = MathHelper.max( -((quoteBalance.amount + insurance).div( liquidationPrice ) + 1), basisAmount

```solidity
);
...
```

Note that quoteBalance.amount + insurance may be negative, which would mean that abs(basisAmount) could be increased, leading to incorrect states.

## Proof of Concept

No PoC provided.

## Recommendation

Add if (quoteBalance.amount + insurance <= 0) basisAmount = 0 or similar.
